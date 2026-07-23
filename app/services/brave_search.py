import logging
import httpx
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)


class BraveSearchService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.brave_search_api_key

    async def search(self, query: str, count: int = 5) -> List[Dict[str, Any]]:
        """
        Performs web search via Brave Search API.
        Returns a list of search result items with title, url, description, and snippet.
        """
        api_key = self.api_key or settings.brave_search_api_key
        if not api_key:
            logger.warning("BRAVE_SEARCH_API_KEY is missing!")
            return []

        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key
        }
        params = {
            "q": query,
            "count": min(count, 10)
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers, params=params)
                if response.status_code != 200:
                    logger.error(f"Brave Search API error ({response.status_code}): {response.text[:200]}")
                    return []

                data = response.json()
                results = []
                web_items = data.get("web", {}).get("results", [])
                for item in web_items:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "description": item.get("description", ""),
                        "extra_snippets": item.get("extra_snippets", [])
                    })
                return results
        except Exception as e:
            logger.error(f"Exception during Brave Search: {e}")
            return []

    def format_results_for_llm(self, results: List[Dict[str, Any]]) -> str:
        """
        Formats search results into a clean string for LLM synthesis.
        """
        if not results:
            return "Không tìm thấy kết quả tìm kiếm."

        formatted = ["=== KẾT QUẢ TÌM KIẾM THỜI GIAN THỰC (BRAVE SEARCH) ==="]
        for idx, res in enumerate(results, 1):
            formatted.append(f"\n[{idx}] {res['title']}")
            formatted.append(f"    Link: {res['url']}")
            formatted.append(f"    Mô tả: {res['description']}")
            if res.get("extra_snippets"):
                snippets = " ".join(res["extra_snippets"][:2])
                formatted.append(f"    Chi tiết: {snippets}")

        return "\n".join(formatted)


brave_search = BraveSearchService()
