# Aegis Assistant Backend

Backend RESTful API & AI Agent Runtime cho ứng dụng **Aegis Assistant**, được triển khai bằng **Python 3.13**, **FastAPI**, và tích hợp mô hình **Google Gemini (`gemini-3.1-flash-lite`)**.

## 🚀 Tính Năng Chính
- **AI Agent Runtime**:
  - `POST /api/gemini/briefing`: Sinh bản tin sáng thông minh dựa trên trạng thái Tasks, Servers, và Notifications.
  - `POST /api/gemini/chat`: Trò chuyện đa lượt với Trợ lý ảo Aegis, nhận diện ngữ cảnh và kiến trúc hệ thống.
  - `POST /api/gemini/news`: Tổng hợp tin tức công nghệ / Android 16 mới nhất với Google Search Grounding.
- **RESTful Data Management**:
  - Task Management (`/api/tasks`)
  - Server Health & Latency Monitoring / Ping (`/api/servers` & `/api/servers/ping`)
  - System Notifications (`/api/notifications`)
  - Assistant Settings & Theme Config (`/api/config`)
- **CORS & Connection Handling**: Hỗ trợ đầy đủ Origin từ WebView Android APK (Capacitor) và ngắt tiến trình AI khi Client Abort Request.

## 🛠️ Cài Đặt & Khởi Chạy

### 1. Cài đặt Virtualenv & Thư viện
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Cấu hình biến môi trường `.env`
Tạo tệp `.env` từ tệp mẫu `.env.example`:
```bash
cp .env.example .env
```
Cập nhật tệp `.env`:
```env
PORT=3000
GEMINI_API_KEY=your_actual_gemini_api_key
GEMINI_MODEL=gemini-3.1-flash-lite
DATABASE_URL=sqlite:///./aegis.db
```

### 3. Chạy Server Backend
```bash
python3 run.py
```
Server sẽ lắng nghe tại `http://localhost:3000`.  
Tài liệu tương tác Swagger UI: `http://localhost:3000/docs`.

---

*Phát triển bởi Aegis AI Team.*
