import re
import os
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.schemas.gemini import BriefingRequest, ChatRequest, NewsRequest, NewsResponse, ChatMessage
from app.schemas.notification import NotificationItem
from app.agent.gemini_client import gemini_client
from app.agent.tools import analyze_task_health, analyze_server_health
from app.models.db_models import UserDB

logger = logging.getLogger(__name__)


def _sync_to_markdown_file(category: str, key: str, value: str, user_email: str):
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        memories_dir = os.path.join(base_dir, "memories", user_email)
        user_md_path = os.path.join(memories_dir, "USER.md")
        memory_md_path = os.path.join(memories_dir, "MEMORY.md")

        if not os.path.exists(memories_dir):
            os.makedirs(memories_dir, exist_ok=True)

        target_file = memory_md_path if category in ("tech_stack", "habit") else user_md_path

        if not os.path.exists(target_file):
            if target_file == user_md_path:
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write("# Hồ sơ Chủ nhân (USER.md)\n\nTệp tin này lưu trữ các đặc điểm cá nhân, vai trò, sở thích và chỉ thị riêng của chủ nhân.\n\n## Thông tin chung\n- Tên: Nam\n- Vai trò: AI Developer & Security Expert\n\n## Chỉ thị phong cách làm việc\n")
            else:
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write("# Chỉ thị Công nghệ & Quy tắc Dự án (MEMORY.md)\n\nTệp tin này lưu trữ môi trường công nghệ, quy tắc dự án và các bài học kinh nghiệm.\n\n## Môi trường & Tech Stack\n- OS: Linux Ubuntu\n- Backend: Python FastAPI, SQLite\n- Frontend: React TypeScript, Tailwind CSS\n- Native: Capacitor (Android)\n\n## Hướng dẫn dự án & Server\n")

        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()

        escaped_key = re.escape(key)
        pattern = rf"(?i)-\s*{escaped_key}\s*:\s*[^\n]+"

        if re.search(pattern, content):
            new_content = re.sub(pattern, f"- {key}: {value}", content)
        else:
            if not content.endswith("\n"):
                content += "\n"
            new_content = content + f"- {key}: {value}\n"

        with open(target_file, "w", encoding="utf-8") as f:
            f.write(new_content)
        logger.info(f"🧠 [Hermes Memory] Synced '{key}' to Markdown file '{os.path.basename(target_file)}'")
    except Exception as e:
        logger.error(f"Failed to sync memory to Markdown file: {e}")


def _delete_from_markdown_file(key: str, user_email: str):
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        memories_dir = os.path.join(base_dir, "memories", user_email)
        user_md_path = os.path.join(memories_dir, "USER.md")
        memory_md_path = os.path.join(memories_dir, "MEMORY.md")

        for target_file in [user_md_path, memory_md_path]:
            if os.path.exists(target_file):
                with open(target_file, "r", encoding="utf-8") as f:
                    content = f.read()
                escaped_key = re.escape(key)
                pattern = rf"(?i)-\s*{escaped_key}\s*:\s*[^\n]+\n?"
                if re.search(pattern, content):
                    new_content = re.sub(pattern, "", content)
                    with open(target_file, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    logger.info(f"🧠 [Hermes Memory] Deleted key '{key}' from Markdown file '{os.path.basename(target_file)}'")
    except Exception as e:
        logger.error(f"Failed to delete memory from Markdown file: {e}")


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
            f"Hãy đóng vai {assistant_name}. Hãy tổng hợp một bản tin tóm tắt (Briefing) ngắn gọn, chuẩn xác và đúng trọng tâm dựa trên dữ liệu ngữ cảnh sau đây.\n"
            f"- Tập trung trực tiếp vào nội dung các công việc (Tasks), máy chủ (Servers), thông báo (Notifications) và các tác vụ do người dùng yêu cầu.\n"
            f"- Trình bày tự nhiên, linh hoạt, đi thẳng vào vấn đề chính mà không lan man sang các chủ đề không liên quan hoặc tự chèn từ khóa kỹ thuật thừa thãi.\n\n"
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

    async def handle_chat(self, req: ChatRequest, user: UserDB) -> tuple[str, str]:
        """
        Handles multi-turn AI chatbot conversation with real-time Vietnam context,
        persists conversation history, and dynamically leverages Hermes Memory Engine.
        """
        time_ctx = _get_current_time_context()
        base_instruction = req.systemInstruction or "Bạn là Aegis, trợ lý ảo cá nhân..."

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

        # Only inject tech-stack/project memory (MEMORY.md) when the current question
        # is actually about tech/dev/ops — prevents it from bleeding into unrelated
        # topics like weather, news, or general chit-chat.
        tech_keywords = [
            "code", "lập trình", "developer", "dev ", "devops", "deploy", "docker",
            "kubernetes", "k8s", "server", "máy chủ", "database", "sql", "api",
            "backend", "frontend", "git", "python", "javascript", "typescript",
            "react", "fastapi", "linux", "ubuntu", "ssh", "nginx", "ci/cd",
            "container", "terminal", "script", "config", "bug", "lỗi hệ thống",
            "capacitor", "android studio", "gradle"
        ]
        is_tech_topic = bool(last_user_msg) and any(kw in last_user_msg.lower() for kw in tech_keywords)

        # Read USER.md & MEMORY.md directly (Hermes memory engine architecture)
        memory_ctx = ""
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            memories_dir = os.path.join(base_dir, "memories", user.email)
            user_md_path = os.path.join(memories_dir, "USER.md")
            memory_md_path = os.path.join(memories_dir, "MEMORY.md")

            if not os.path.exists(memories_dir):
                os.makedirs(memories_dir, exist_ok=True)
            if not os.path.exists(user_md_path):
                with open(user_md_path, "w", encoding="utf-8") as f:
                    f.write("# Hồ sơ Chủ nhân (USER.md)\n\nTệp tin này lưu trữ các đặc điểm cá nhân, vai trò, sở thích và chỉ thị riêng của chủ nhân.\n\n## Thông tin chung\n- Tên: Nam\n- Vai trò: AI Developer & Security Expert\n\n## Chỉ thị phong cách làm việc\n")
            if not os.path.exists(memory_md_path):
                with open(memory_md_path, "w", encoding="utf-8") as f:
                    f.write("# Chỉ thị Công nghệ & Quy tắc Dự án (MEMORY.md)\n\nTệp tin này lưu trữ môi trường công nghệ, quy tắc dự án và các bài học kinh nghiệm.\n\n## Môi trường & Tech Stack\n- OS: Linux Ubuntu\n- Backend: Python FastAPI, SQLite\n- Frontend: React TypeScript, Tailwind CSS\n- Native: Capacitor (Android)\n\n## Hướng dẫn dự án & Server\n")

            user_md_content = ""
            with open(user_md_path, "r", encoding="utf-8") as f:
                user_md_content = f.read().strip()

            memory_ctx = (
                "=== BỘ NHỚ LÝ LỊCH VỀ CHỦ NHÂN (HERMES MEMORY ENGINE) ===\n"
                f"--- USER PROFILE (USER.md) ---\n{user_md_content}\n\n"
            )

            if is_tech_topic:
                memory_md_content = ""
                with open(memory_md_path, "r", encoding="utf-8") as f:
                    memory_md_content = f.read().strip()
                memory_ctx += (
                    f"--- CONVENTIONS & LESSONS (MEMORY.md) ---\n{memory_md_content}\n\n"
                    "Hãy vận dụng linh hoạt bộ nhớ trên để tự động cá nhân hóa câu trả lời và làm việc thấu hiểu chủ nhân.\n"
                )
            else:
                memory_ctx += (
                    "Chỉ dùng thông tin USER PROFILE trên để xưng hô/cá nhân hóa giọng văn. "
                    "TUYỆT ĐỐI KHÔNG tự chèn các chi tiết công nghệ, tech stack, server, quy tắc dự án vào câu trả lời "
                    "vì câu hỏi hiện tại KHÔNG liên quan tới chủ đề kỹ thuật/công nghệ.\n"
                )
        except Exception as e:
            logger.warning(f"Could not load Markdown memory files (USER.md/MEMORY.md): {e}")

        system_instruction = f"{base_instruction}\n\n{memory_ctx}\n\n{time_ctx}"

        # Construct dynamic agent thinking log (Hermes thinking simulation)
        thinking_lines = [
            "Đang phân tích tin nhắn và tệp đính kèm của chủ nhân...",
            f"Đã chèn ngữ cảnh thời gian thực tế: {datetime.now().strftime('%H:%M:%S (%d/%m/%Y)')}"
        ]

        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            user_md_path = os.path.join(base_dir, "memories", user.email, "USER.md")
            memory_md_path = os.path.join(base_dir, "memories", user.email, "MEMORY.md")

            if os.path.exists(user_md_path):
                thinking_lines.append("Đọc bộ nhớ chủ nhân (USER.md): Đã nạp đặc điểm và phong cách giao tiếp cá nhân.")
            if is_tech_topic and os.path.exists(memory_md_path):
                thinking_lines.append("Đọc bộ nhớ dự án (MEMORY.md): Đã nạp môi trường công nghệ và quy tắc vận hành (câu hỏi liên quan kỹ thuật).")
            elif os.path.exists(memory_md_path):
                thinking_lines.append("Bỏ qua bộ nhớ dự án (MEMORY.md): Câu hỏi không liên quan tới kỹ thuật/công nghệ.")
        except Exception:
            pass

        # Check if user message warrants real-time web search via Brave Search
        search_keywords = ["tìm", "search", "tra cứu", "thời tiết", "tin tức", "mới nhất", "hôm nay", "giá", "sự kiện", "bài báo", "cập nhật"]
        if last_user_msg and any(kw in last_user_msg.lower() for kw in search_keywords):
            try:
                from app.services.brave_search import brave_search
                thinking_lines.append(f"🔍 [Brave Search Engine] Đang thực hiện tìm kiếm web thời gian thực cho: '{last_user_msg[:50]}'...")
                s_results = await brave_search.search(last_user_msg, count=5)
                if s_results:
                    search_str = brave_search.format_results_for_llm(s_results)
                    system_instruction += (
                        f"\n\n{search_str}\n\n"
                        f"⚠️ YÊU CẦU QUAN TRỌNG VỀ NỘI DUNG VÀ DỮ LIỆU:\n"
                        f"1. Người dùng cần THÔNG TIN CHI TIẾT VÀ DỮ LIỆU THỰC TẾ (ví dụ: nhiệt độ/độ ẩm/sức gió/chỉ số UV 5 ngày tới nếu hỏi thời tiết, nội dung diễn biến/tên repository hot/tính năng mới nếu hỏi tin tức/HackerNews/GitHub), KHÔNG ĐƯỢC chỉ đưa ra tên báo hay danh sách link nguồn tin.\n"
                        f"2. Hãy đi thẳng vào trình bày chi tiết các số liệu, con số và dữ liệu thu thập được."
                    )
                    thinking_lines.append(f"✅ [Brave Search] Đã lấy thành công {len(s_results)} kết quả web thực tế và nạp vào LLM.")
            except Exception as se:
                logger.warning(f"Brave Search integration error: {se}")

        thinking_lines.append("Gửi toàn bộ ngữ cảnh và lịch sử trò chuyện sang mô hình Gemini để suy nghĩ phản hồi...")
        thinking_text = "\n".join(thinking_lines)

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
                    user_id=user.id,
                    role="user",
                    content=last_user_msg,
                    image=last_user_img,
                    file=last_user_file,
                    fileName=last_user_fileName,
                    thinking=None,
                    timestamp=now_str,
                    created_at=iso_now
                )
                db.add(user_db_msg)

            # Save model response
            model_db_msg = ChatMessageDB(
                id=f"msg_model_{int(time.time()*1000)}",
                user_id=user.id,
                role="model",
                content=response_text,
                image=None,
                file=None,
                fileName=None,
                thinking=thinking_text,
                timestamp=now_str,
                created_at=iso_now
            )
            db.add(model_db_msg)
            db.commit()
            db.close()

            # Trigger background memory extraction loop (Hermes Learning)
            if last_user_msg and len(last_user_msg.strip()) > 5:
                import asyncio
                asyncio.create_task(self._extract_and_learn_memories(last_user_msg, response_text, user))

        except Exception as e:
            logger.error(f"Error persisting chat history: {e}")

        return response_text, thinking_text

    async def _extract_and_learn_memories(self, user_msg: str, model_reply: str, user: UserDB):
        """
        Hermes Learning Engine: Analyzes user conversation turns to extract
        permanent facts, preferences, technology stacks, or user habits.
        """
        try:
            extraction_prompt = (
                f"Hãy đóng vai hệ thống phân tích bộ nhớ Hermes Memory cho trợ lý AI Aegis.\n"
                f"Phân tích tin nhắn của người dùng sau đây:\n"
                f"người dùng: \"{user_msg}\"\n\n"
                f"Nhiệm vụ: Hãy lọc tìm xem trong tin nhắn có chứa THÔNG TIN CÁ NHÂN quan trọng (tên, chức vụ, vai trò), MÔI TRƯỜNG CÔNG NGHỆ/HỆ ĐIỀU HÀNH (VD: Ubuntu, Docker, Node.js), hoặc NGUYÊN TẮC CÁ NHÂN lâu dài nào thực sự cần thiết cho công việc hay không.\n"
                f"QUY TẮC LỌC NGHIÊM NGẶT:\n"
                f"1. TUYỆT ĐỐI KHÔNG lưu các thông tin vụn vặt, trò chuyện phiếm, sở thích động vật/thú cưng, đồ ăn, phim ảnh, thời tiết, hoặc các câu hỏi nhất thời mang tính chất tán gẫu (VD: thích mèo, thích chó, thích ăn pizza... -> BỎ QUA, has_memory: false).\n"
                f"2. Chỉ lưu những thông tin kỹ thuật, thông tin định danh người dùng, hoặc hướng dẫn phong cách làm việc có tính chất lâu dài và thực sự giúp ích cho trợ lý quản trị hệ thống.\n\n"
                f"Nếu CÓ thông tin thỏa mãn, hãy trả về 1 JSON Object duy nhất:\n"
                f'{{\n  "has_memory": true,\n  "category": "preference" hoặc "tech_stack" hoặc "fact" || "habit",\n  "key": "Tên đặc trưng ngắn gọn (bằng tiếng Anh viết thường hoặc tiếng Việt ngắn gọn, ví dụ: user_name, main_os, preferred_db)",\n  "value": "Mô tả chi tiết bằng Tiếng Việt"\n}}\n'
                f'Nếu KHÔNG CÓ thông tin công việc/cá nhân cốt lõi nào cần ghi nhớ lâu dài, trả về:\n'
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

                # Sync to Markdown file
                _sync_to_markdown_file(category, mem_key, mem_val, user.email)

                # Check if memory key exists in DB for this user
                existing = db.query(UserMemoryDB).filter(
                    UserMemoryDB.key == mem_key,
                    UserMemoryDB.user_id == user.id
                ).first()
                iso_now = datetime.now().isoformat()
                if existing:
                    existing.value = mem_val
                    existing.updated_at = iso_now
                    logger.info(f"🧠 [Hermes Memory] Updated memory '{mem_key}': {mem_val}")
                else:
                    new_mem = UserMemoryDB(
                        id=f"mem_{int(time.time()*1000)}",
                        user_id=user.id,
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

        weather_keywords = ["thời tiết", "nhiệt độ", "dự báo", "mưa", "weather", "forecast"]
        is_weather_topic = any(kw in custom_topic.lower() for kw in weather_keywords)

        from app.services.brave_search import brave_search
        search_query = custom_topic
        if is_weather_topic:
            search_query = f"{custom_topic} nhiệt độ độ ẩm tốc độ gió chỉ số UV khả năng mưa hôm nay và 5 ngày tới"
        b_results = await brave_search.search(query=search_query, count=5)
        search_ctx = brave_search.format_results_for_llm(b_results)

        if is_weather_topic:
            topic_specific_note = (
                f" Đây là chủ đề THỜI TIẾT: BẮT BUỘC trích xuất nhiệt độ (°C, cao nhất/thấp nhất), độ ẩm (%), "
                f"tốc độ gió (km/h), chỉ số UV, và khả năng mưa (%) cho từng ngày có dữ liệu."
            )
        else:
            topic_specific_note = ""

        data_requirements = (
            f"1. BẮT BUỘC trích xuất và trình bày SỐ LIỆU, CON SỐ, TÊN RIÊNG CỤ THỂ (ví dụ: số liệu thống kê, giá cả, "
            f"tên sản phẩm/phiên bản/repository/công ty, mốc thời gian chính xác) từ dữ liệu Brave Search ở trên.{topic_specific_note}\n"
            f"2. TUYỆT ĐỐI KHÔNG được viết chung chung, mơ hồ kiểu 'có nhiều diễn biến mới', 'cần lưu ý', 'cẩn trọng' "
            f"mà không kèm dữ liệu cụ thể phía sau. Nếu một mục thiếu dữ liệu cụ thể, hãy nêu rõ những gì có và bỏ qua "
            f"phần thiếu, không được thay thế bằng câu chung chung.\n"
            f"3. Sử dụng dữ liệu thực tế từ Brave Search, trích dẫn đúng `sourceUrl` thực tế từ bài viết tìm kiếm được."
        )

        prompt = (
            f"{time_ctx}\n\n"
            f"{search_ctx}\n\n"
            f"Bạn là hệ thống điểm tin {'thời tiết' if is_weather_topic else 'công nghệ'} tự động thời gian thực cho Aegis Assistant tại Việt Nam.\n"
            f"Nhiệm vụ: Dựa trên kết quả tìm kiếm thời gian thực (Brave Search) ở trên, hãy tổng hợp 3 tin tức MỚI NHẤT tính tới ngày {today_date} về chủ đề: '{custom_topic}'.\n\n"
            f"YÊU CẦU THỜI GIAN & ĐỊNH DẠNG:\n"
            f"{data_requirements}\n"
            f"4. Trả về duy nhất 1 JSON Array gồm đúng 3 JSON Object có cấu trúc chính xác sau:\n"
            f"[\n"
            f"  {{\n"
            f'    "title": "Tiêu đề tin tức mới nhất tính đến hôm nay {today_date}",\n'
            f'    "description": "Tóm tắt ngắn 1-2 câu về sự kiện mới.",\n'
            f'    "category": "news",\n'
            f'    "contentDetail": "Chi tiết tin tức 2-3 đoạn văn bản Markdown tổng hợp diễn biến mới nhất, bắt buộc kèm số liệu/con số/tên riêng cụ thể{" (nhiệt độ, độ ẩm, gió, UV, % mưa)" if is_weather_topic else ""}, không viết chung chung.",\n'
            f'    "sourceUrl": "Link URL thực tế từ kết quả tìm kiếm Brave Search"\n'
            f"  }}\n"
            f"]\n"
            f"Chú ý: Trong các chuỗi text JSON, không dùng ký tự xuống dòng trực tiếp mà dùng \\n."
        )

        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        
        raw_output = await self.gemini.generate_content(
            contents=contents,
            system_instruction=(
                f"Bạn là AI chuyên gia tổng hợp tin tức từ kết quả Brave Search tại Việt Nam ngày {today_date}. "
                f"Trả về JSON array hợp lệ 100%. Luôn ưu tiên số liệu, con số, tên riêng cụ thể thay vì nhận định chung chung."
                + (
                    " Khi chủ đề là thời tiết, bắt buộc có nhiệt độ, độ ẩm, gió, UV, % mưa cụ thể."
                    if is_weather_topic else ""
                )
            ),
            temperature=0.4,
            google_search_grounding=False,
            json_mode=False,
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
