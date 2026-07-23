import re
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.schemas.gemini import BriefingRequest, ChatRequest, NewsRequest, NewsResponse, ChatMessage
from app.schemas.notification import NotificationItem
from app.agent.gemini_client import gemini_client
from app.agent.tools import analyze_task_health, analyze_server_health

logger = logging.getLogger(__name__)


def _get_current_time_context() -> str:
    """
    Returns real-time timestamp and location context for Vietnam (UTC+7).
    """
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    date_str = now.strftime("%d/%m/%Y")
    return (
        f"=== THỜI GIAN & ĐỊA ĐIỂM THỰC TẾ HỆ THỐNG ===\n"
        f"- Quốc gia / Vùng miền: Việt Nam (UTC+7, Asia/Ho_Chi_Minh)\n"
        f"- Thời điểm thực tế hiện tại: {now_str} (Ngày {date_str})\n"
        f"- Quy tắc thời gian: Ưu tiên tin tức và thông tin mới nhất tính tới hôm nay ({date_str}), tuyệt đối không lấy tin tức cũ lỗi thời.\n"
    )


def _repair_and_parse_json(raw_text: str) -> Any:
    """
    Cleans and repairs raw text output from LLMs to ensure strict JSON parsing.
    Handles unescaped control characters, newlines inside strings, markdown codeblocks,
    and includes a regex chunk extraction fallback.
    """
    clean_text = raw_text.strip()

    # Remove markdown code fences if present
    if clean_text.startswith("```"):
        lines = clean_text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        clean_text = "\n".join(lines).strip()

    # Attempt 1: Direct JSON parse
    try:
        return json.loads(clean_text, strict=False)
    except Exception:
        pass

    # Attempt 2: Escape raw unescaped newlines/control characters inside string values
    try:
        def _escape_control_chars(match):
            s = match.group(0)
            return s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")

        repaired = re.sub(r'"([^"\\]|\\.)*"', _escape_control_chars, clean_text, flags=re.DOTALL)
        return json.loads(repaired, strict=False)
    except Exception:
        pass

    # Attempt 3: Regex chunk extraction fallback
    items = []
    chunks = re.split(r'\{\s*"title"', clean_text)
    for chunk in chunks[1:]:
        chunk = '{"title"' + chunk
        title_match = re.search(r'"title"\s*:\s*"([^"]+)"', chunk)
        desc_match = re.search(r'"description"\s*:\s*"([^"]+)"', chunk)
        content_match = re.search(r'"contentDetail"\s*:\s*"([^"]+)"', chunk)
        url_match = re.search(r'"sourceUrl"\s*:\s*"([^"]+)"', chunk)

        if title_match or desc_match:
            items.append({
                "title": title_match.group(1) if title_match else "Tin tức công nghệ mới",
                "description": desc_match.group(1) if desc_match else "Cập nhật từ Aegis AI",
                "category": "news",
                "contentDetail": content_match.group(1) if content_match else (desc_match.group(1) if desc_match else ""),
                "sourceUrl": url_match.group(1) if url_match else "https://news.google.com"
            })

    if items:
        return items

    raise ValueError("Could not parse valid news JSON structure")


class AgentRuntime:
    def __init__(self):
        self.gemini = gemini_client

    async def generate_daily_briefing(self, req: BriefingRequest) -> str:
        """
        Synthesizes tasks, servers, and notification status with real-time Vietnam context.
        """
        assistant_name = req.assistantName or "Aegis"
        custom_prompt = req.customPrompt or "Bạn là Aegis, trợ lý ảo cá nhân..."

        time_ctx = _get_current_time_context()
        tasks = req.tasks or []
        servers = req.servers or []
        notifications = req.notifications or []

        task_summary = analyze_task_health(tasks)
        server_summary = analyze_server_health(servers)

        context_parts = [time_ctx]
        context_parts.append("=== TRẠNG THÁI HỆ THỐNG HIỆN TẠI ===")
        context_parts.append(f"- Tổng số công việc: {task_summary['total']} (Đã xong: {task_summary['completed']}, Đang chờ: {task_summary['pending']})")
        if task_summary["high_priority_pending_count"] > 0:
            context_parts.append(f"- CÔNG VIỆC ƯU TIÊN CAO CHƯA HOÀN THÀNH ({task_summary['high_priority_pending_count']}):")
            for t in task_summary["high_priority_tasks"]:
                context_parts.append(f"  + [{t.get('title')}] (Hạn chót: {t.get('deadline', 'Chưa có')})")

        context_parts.append(f"\n- Tổng số máy chủ: {server_summary['total']}")
        if server_summary["down_count"] > 0:
            context_parts.append(f"  ⚠️ MÁY CHỦ BỊ DOWN ({server_summary['down_count']}): {[s.get('name') for s in server_summary['down_servers']]}")
        if server_summary["degraded_count"] > 0:
            context_parts.append(f"  ⚠️ MÁY CHỦ CHẬM/DEGRADED ({server_summary['degraded_count']}): {[s.get('name') for s in server_summary['degraded_servers']]}")
        if server_summary["high_ram_servers"]:
            context_parts.append(f"  ⚠️ MÁY CHỦ CAO RAM: {[s.get('name') for s in server_summary['high_ram_servers']]}")

        if notifications:
            unread = sum(1 for n in notifications if not n.get("read"))
            context_parts.append(f"\n- Thông báo chưa đọc: {unread}/{len(notifications)}")

        user_prompt = (
            f"Hãy đóng vai {assistant_name}. Dựa trên dữ liệu thời gian thực tế và ngữ cảnh hệ thống sau đây, hãy viết một bản tin tóm tắt đầu ngày "
            f"(Daily Briefing) thông minh, súc tích, truyền cảm hứng và điểm qua các công việc quan trọng / cảnh báo máy chủ cho chủ nhân tại Việt Nam.\n\n"
            + "\n".join(context_parts)
        )

        contents = [{"role": "user", "parts": [{"text": user_prompt}]}]
        briefing_text = await self.gemini.generate_content(
            contents=contents,
            system_instruction=custom_prompt + "\n\n" + time_ctx,
            temperature=0.7,
            max_retries_per_model=3
        )
        return briefing_text

    async def handle_chat(self, req: ChatRequest) -> str:
        """
        Handles multi-turn AI chatbot conversation with real-time Vietnam context,
        persists conversation history, and dynamically leverages Hermes Memory Engine.
        """
        time_ctx = _get_current_time_context()
        base_instruction = req.systemInstruction or "Bạn là Aegis, trợ lý ảo cá nhân..."

        # Fetch active Hermes User Memories from DB
        memory_ctx = ""
        try:
            from app.db import SessionLocal
            from app.models.db_models import UserMemoryDB, ChatMessageDB
            db = SessionLocal()
            memories = db.query(UserMemoryDB).all()
            if memories:
                memory_lines = [f"- [{m.category.upper()}] {m.key}: {m.value}" for m in memories]
                memory_ctx = (
                    "=== BỘ NHỚ LÝ LỊCH VỀ CHỦ NHÂN (HERMES MEMORY STORE) ===\n"
                    "Hệ thống đã tự động ghi nhớ các điểm quan trọng sau về chủ nhân qua các cuộc trò chuyện trước:\n"
                    + "\n".join(memory_lines) + "\n"
                    "Hãy vận dụng linh hoạt bộ nhớ trên để trả lời tự nhiên, thấu hiểu cá nhân hóa chủ nhân mà không cần chủ nhân nhắc lại.\n"
                )
            db.close()
        except Exception as e:
            logger.warning(f"Could not load Hermes User Memories: {e}")

        system_instruction = f"{base_instruction}\n\n{memory_ctx}\n\n{time_ctx}"

        contents = []
        last_user_msg = ""
        last_user_img = None
        last_user_file = None
        last_user_fileName = None

        for msg in req.messages:
            role = "model" if msg.role in ("model", "assistant") else "user"
            parts = []
            if msg.image:
                match = re.match(r"^data:(image/\w+);base64,(.+)$", msg.image)
                if match:
                    mime_type, b64_data = match.group(1), match.group(2)
                    parts.append({
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_data
                        }
                    })
            if msg.file:
                match = re.match(r"^data:([^;]+);base64,(.+)$", msg.file)
                if match:
                    mime_type, b64_data = match.group(1), match.group(2)
                    parts.append({
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_data
                        }
                    })
            if msg.content:
                parts.append({"text": msg.content})
            elif not parts:
                parts.append({"text": ""})

            contents.append({
                "role": role,
                "parts": parts
            })

            if role == "user":
                last_user_msg = msg.content or ""
                last_user_img = msg.image
                last_user_file = msg.file
                last_user_fileName = msg.fileName

        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Xin chào Trợ lý Aegis!"}]}]

        response_text = await self.gemini.generate_content(
            contents=contents,
            system_instruction=system_instruction,
            temperature=0.7,
            max_retries_per_model=3
        )

        # Persist Chat Messages & Trigger Background Memory Extraction
        try:
            from app.db import SessionLocal
            from app.models.db_models import ChatMessageDB
            db = SessionLocal()

            now_str = datetime.now().strftime("%H:%M")
            iso_now = datetime.now().isoformat()

            # Save latest user message if non-empty
            if last_user_msg or last_user_img or last_user_file:
                user_db_msg = ChatMessageDB(
                    id=f"msg_user_{int(time.time()*1000)}",
                    role="user",
                    content=last_user_msg,
                    image=last_user_img,
                    file=last_user_file,
                    fileName=last_user_fileName,
                    timestamp=now_str,
                    created_at=iso_now
                )
                db.add(user_db_msg)

            # Save model response
            model_db_msg = ChatMessageDB(
                id=f"msg_model_{int(time.time()*1000)}",
                role="model",
                content=response_text,
                image=None,
                file=None,
                fileName=None,
                timestamp=now_str,
                created_at=iso_now
            )
            db.add(model_db_msg)
            db.commit()
            db.close()

            # Trigger background memory extraction loop (Hermes Learning)
            if last_user_msg and len(last_user_msg.strip()) > 5:
                import asyncio
                asyncio.create_task(self._extract_and_learn_memories(last_user_msg, response_text))

        except Exception as e:
            logger.error(f"Error persisting chat history: {e}")

        return response_text

    async def _extract_and_learn_memories(self, user_msg: str, model_reply: str):
        """
        Hermes Learning Engine: Analyzes user conversation turns to extract
        permanent facts, preferences, technology stacks, or user habits.
        """
        try:
            extraction_prompt = (
                f"Hãy đóng vai hệ thống phân tích bộ nhớ Hermes Memory cho trợ lý AI Aegis.\n"
                f"Phân tích tin nhắn của người dùng sau đây:\n"
                f"người dùng: \"{user_msg}\"\n\n"
                f"Nhiệm vụ: Tìm xem trong tin nhắn có chứa THÔNG TIN CÁ NHÂN, SỞ THÍCH, MÔI TRƯỜNG CÔNG NGHỆ, THÓI QUEN hoặc NGUYÊN TẮC CẦN GHI NHỚ LÂU DÀI nào của người dùng hay không.\n"
                f"Nếu CÓ, hãy trả về 1 JSON Object duy nhất có dạng:\n"
                f'{{\n  "has_memory": true,\n  "category": "preference" hoặc "tech_stack" hoặc "fact" hoặc "habit",\n  "key": "Tên ngắn gọn về đặc điểm",\n  "value": "Mô tả chi tiết bằng Tiếng Việt"\n}}\n'
                f'Nếu KHÔNG CÓ thông tin cá nhân đáng ghi nhớ lâu dài (ví dụ chỉ hỏi chào hỏi đơn thuần, câu hỏi tức thời), trả về:\n'
                f'{{\n  "has_memory": false\n}}'
            )

            contents = [{"role": "user", "parts": [{"text": extraction_prompt}]}]
            raw_res = await self.gemini.generate_content(
                contents=contents,
                system_instruction="Bạn là AI trích xuất bộ nhớ tri thức cá nhân. Trả về JSON duy nhất 100%.",
                temperature=0.2,
                json_mode=True,
                max_retries_per_model=2
            )

            parsed = _repair_and_parse_json(raw_res)
            if isinstance(parsed, dict) and parsed.get("has_memory") and parsed.get("key") and parsed.get("value"):
                from app.db import SessionLocal
                from app.models.db_models import UserMemoryDB
                db = SessionLocal()
                mem_key = parsed["key"].strip()
                mem_val = parsed["value"].strip()
                category = parsed.get("category", "preference").strip()

                # Check if memory key exists
                existing = db.query(UserMemoryDB).filter(UserMemoryDB.key == mem_key).first()
                iso_now = datetime.now().isoformat()
                if existing:
                    existing.value = mem_val
                    existing.updated_at = iso_now
                    logger.info(f"🧠 [Hermes Memory] Updated memory '{mem_key}': {mem_val}")
                else:
                    new_mem = UserMemoryDB(
                        id=f"mem_{int(time.time()*1000)}",
                        category=category,
                        key=mem_key,
                        value=mem_val,
                        confidence=1.0,
                        updated_at=iso_now
                    )
                    db.add(new_mem)
                    logger.info(f"🧠 [Hermes Memory] Learned new memory '{mem_key}': {mem_val}")

                db.commit()
                db.close()
        except Exception as e:
            logger.warning(f"Error in Hermes memory extraction: {e}")

    async def generate_news(self, req: NewsRequest) -> NewsResponse:
        """
        Generates real-time tech news using Search Grounding / Gemini synthesis for Vietnam context.
        """
        time_ctx = _get_current_time_context()
        today_date = datetime.now().strftime("%d/%m/%Y")
        today_year = datetime.now().strftime("%Y")
        
        topic = req.topic or "tech-news"
        custom_topic = req.customTopic or f"Công nghệ AI, Máy chủ & Android năm {today_year}"

        prompt = (
            f"{time_ctx}\n"
            f"Bạn là hệ thống điểm tin công nghệ tự động thời gian thực cho Aegis Assistant tại Việt Nam.\n"
            f"Nhiệm vụ: Hãy tìm kiếm và tổng hợp 3 tin tức công nghệ/hệ thống MỚI NHẤT mới cập nhật tính tới ngày {today_date} về chủ đề: '{custom_topic}'.\n\n"
            f"YÊU CẦU THỜI GIAN & ĐỊNH DẠNG:\n"
            f"1. Tuyệt đối không lấy bài báo hoặc sự kiện cũ từ những năm trước.\n"
            f"2. Trả về duy nhất 1 JSON Array gồm đúng 3 JSON Object có cấu trúc chính xác sau:\n"
            f"[\n"
            f"  {{\n"
            f'    "title": "Tiêu đề tin tức mới nhất tính đến hôm nay {today_date}",\n'
            f'    "description": "Tóm tắt ngắn 1-2 câu về sự kiện mới.",\n'
            f'    "category": "news",\n'
            f'    "contentDetail": "Chi tiết tin tức 2-3 đoạn văn bản Markdown tổng hợp diễn biến mới nhất.",\n'
            f'    "sourceUrl": "https://news.google.com"\n'
            f"  }}\n"
            f"]\n"
            f"Chú ý: Trong các chuỗi text JSON, không dùng ký tự xuống dòng trực tiếp mà dùng \\n."
        )

        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        
        raw_output = await self.gemini.generate_content(
            contents=contents,
            system_instruction=f"Bạn là AI chuyên gia tổng hợp tin tức công nghệ thời gian thực tại Việt Nam ngày {today_date}. Trả về JSON array hợp lệ 100%.",
            temperature=0.4,
            google_search_grounding=True,
            json_mode=False,  # Keep search grounding enabled for live news search
            max_retries_per_model=3
        )

        news_items: List[NotificationItem] = []
        now_time = datetime.now().strftime("%H:%M")

        first_title = None
        first_desc = None
        first_content = None
        first_source = None

        try:
            parsed = _repair_and_parse_json(raw_output)
            if isinstance(parsed, list):
                for idx, item in enumerate(parsed[:5]):
                    notif_id = f"notif_news_{int(time.time() * 1000)}_{idx}"
                    title = item.get("title", f"Tin tức công nghệ mới #{idx+1}")
                    desc = item.get("description", "Không có mô tả chi tiết.")
                    content_detail = item.get("contentDetail", desc)
                    source_url = item.get("sourceUrl", "https://news.google.com")

                    if idx == 0:
                        first_title = title
                        first_desc = desc
                        first_content = content_detail
                        first_source = source_url

                    news_items.append(NotificationItem(
                        id=notif_id,
                        title=title,
                        description=desc,
                        category="news",
                        read=False,
                        timestamp=now_time
                    ))
        except Exception as e:
            logger.warning(f"Failed to parse news JSON from Gemini: {e}. Raw text was: {raw_output[:200]}")
            first_title = f"Tin tức mới nhất ({today_date}): {custom_topic}"
            first_desc = f"Cập nhật những diễn biến công nghệ nổi bật tính tới ngày {today_date} tại Việt Nam."
            first_content = f"### {first_title}\n\n{first_desc}\n\nHệ thống Aegis Assistant đã tự động tổng hợp tin tức mới nhất cho bạn."
            first_source = "https://ai.google.dev"

            news_items.append(NotificationItem(
                id=f"notif_news_{int(time.time() * 1000)}_1",
                title=first_title,
                description=first_desc,
                category="news",
                read=False,
                timestamp=now_time
            ))

        if not first_title and news_items:
            first_title = news_items[0].title
            first_desc = news_items[0].description
            first_content = f"### {first_title}\n\n{first_desc}"
            first_source = "https://news.google.com"

        return NewsResponse(
            news=news_items,
            title=first_title or f"Bản tin công nghệ Aegis ({today_date})",
            description=first_desc or "Cập nhật mới nhất từ hệ thống AI",
            contentDetail=first_content or first_desc or "Không có chi tiết.",
            sourceUrl=first_source or "https://news.google.com"
        )


agent_runtime = AgentRuntime()
