import os
import re
import json
import asyncio
import logging
import httpx
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)


def _mask_key(text: str) -> str:
    """Masks API keys in strings and URLs for security."""
    if not text:
        return text
    return re.sub(r'key=[A-Za-z0-9_\.-]+', 'key=***REDACTED***', text)


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.primary_model = default_model or settings.gemini_model or "gemini-3.1-flash-lite"
        self.fallback_models = [
            self.primary_model,
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash"
        ]
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time = 0.0
        self.min_request_interval = 1.0  # Min 1s delay between consecutive calls

    async def _enforce_rate_limit(self):
        """Ensures consecutive API requests respect RPM limits."""
        async with self._rate_limit_lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self.min_request_interval:
                await asyncio.sleep(self.min_request_interval - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    async def generate_content(
        self,
        contents: List[Dict[str, Any]],
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        google_search_grounding: bool = False,
        json_mode: bool = False,
        max_retries_per_model: int = 3
    ) -> str:
        """
        Generates text using Google Gemini API with exponential backoff retries & rate-limiting.
        Sanitizes and masks API Key in all log output.
        """
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is missing!")
            return (
                "⚠️ [Aegis Assistant] Cảnh báo: `GEMINI_API_KEY` chưa được cấu hình trong môi trường backend.\n"
                "Vui lòng thiết lập biến môi trường `GEMINI_API_KEY` trong tệp `.env` để kích hoạt AI."
            )

        models_to_try = []
        for m in self.fallback_models:
            if m and m not in models_to_try:
                models_to_try.append(m)

        last_error = None
        async with httpx.AsyncClient(timeout=90.0) as client:
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
                
                generation_config: Dict[str, Any] = {
                    "temperature": temperature,
                    "maxOutputTokens": 4096,
                }
                
                if json_mode:
                    generation_config["responseMimeType"] = "application/json"

                payload: Dict[str, Any] = {
                    "contents": contents,
                    "generationConfig": generation_config
                }
                
                if system_instruction:
                    payload["systemInstruction"] = {
                        "parts": [{"text": system_instruction}]
                    }
                
                if google_search_grounding and not json_mode:
                    payload["tools"] = [{"googleSearch": {}}]

                # Retry loop for the current model
                for attempt in range(1, max_retries_per_model + 1):
                    await self._enforce_rate_limit()

                    try:
                        logger.info(f"Sending request to Gemini model '{model_name}' (Attempt {attempt}/{max_retries_per_model})...")
                        response = await client.post(url, json=payload)
                        
                        if response.status_code == 200:
                            data = response.json()
                            candidates = data.get("candidates", [])
                            if candidates and "content" in candidates[0]:
                                parts = candidates[0]["content"].get("parts", [])
                                text_pieces = [p.get("text", "") for p in parts if "text" in p]
                                if text_pieces:
                                    return "".join(text_pieces)
                            return "Dữ liệu phản hồi từ Gemini không có nội dung văn bản."

                        elif response.status_code == 429:
                            # Rate limit / Quota exceeded
                            error_text = _mask_key(response.text)
                            logger.warning(f"Rate limit 429 on model {model_name} (Attempt {attempt}). Response: {error_text[:150]}")
                            last_error = f"Rate limit 429 ({model_name}): {error_text[:120]}"
                            
                            # If Search Grounding tool caused 429 quota block, strip search tool for next attempt
                            if "tools" in payload:
                                logger.info("Google Search Grounding quota limit hit. Disabling search tool for retry...")
                                payload.pop("tools", None)

                            if attempt < max_retries_per_model:
                                backoff_delay = 1.5 * attempt
                                logger.info(f"Backing off for {backoff_delay}s before retrying model {model_name}...")
                                await asyncio.sleep(backoff_delay)
                                continue
                            else:
                                logger.warning(f"Max retries reached for model {model_name}. Trying next fallback model...")
                                break

                        elif response.status_code in (404, 400) and ("NOT_FOUND" in response.text or "invalid model" in response.text.lower()):
                            masked_resp = _mask_key(response.text)
                            logger.warning(f"Model {model_name} unsupported/not found. Skipping retries for this model...")
                            last_error = masked_resp[:120]
                            break
                        else:
                            masked_resp = _mask_key(response.text)
                            logger.error(f"Gemini API Error ({response.status_code}): {masked_resp[:200]}")
                            last_error = f"Gemini API Error ({response.status_code}): {masked_resp[:120]}"
                            if attempt < max_retries_per_model:
                                await asyncio.sleep(2.0)
                                continue
                            break

                    except Exception as e:
                        masked_err = _mask_key(str(e))
                        logger.error(f"Gemini request exception with model {model_name}: {masked_err}")
                        last_error = masked_err
                        if attempt < max_retries_per_model:
                            await asyncio.sleep(2.0)
                            continue
                        break

        return f"Không thể kết nối tới mô hình AI Gemini. Chi tiết lỗi: {_mask_key(str(last_error))}"


# Singleton instance
gemini_client = GeminiClient()
