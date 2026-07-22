# Aegis Assistant — Tài Liệu Kiến Trúc & Đặc Tả Backend (Backend Specification)

Tài liệu này tổng hợp toàn bộ cấu trúc dữ liệu, các endpoint API, luồng xử lý và yêu cầu kỹ thuật của hệ thống **Aegis Assistant** nhằm phục vụ việc thiết kế và lập trình Backend.

---

## 1. Tổng Quan Hệ Thống (System Overview)

* **Tên ứng dụng:** Aegis Assistant (Trợ lý cá nhân & Quản trị hệ thống)
* **Frontend Mobile / Web:** React (TypeScript), Vite, TailwindCSS, Framer Motion, Capacitor (Biên dịch APK Android Native Edge-to-Edge).
* **Vai trò của Backend:**
  - Cung cấp dữ liệu và lưu trữ tập trung (Tasks, Server Monitoring, Notifications, Assistant Config).
  - Tích hợp mô hình AI (Google Gemini API) để sinh **Bản tin sáng (Daily Briefing)**, **Trò chuyện trợ lý ảo (AI Chatbot)**, và **Tin tức công nghệ/Hệ thống (Search Grounding News)**.
  - Xử lý kiểm tra trạng thái máy chủ (Server Health Check / Uptime Ping).
  - Cho phép thiết lập động IP/Domain Backend qua trang Cài đặt ứng dụng (`apiBaseUrl`).

---

## 2. Mô Hình Dữ Liệu Chi Tiết (Data Models & Database Schemas)

### 2.1. Task (Nhiệm vụ)
| Field | Type | Description | Constraints / Examples |
|---|---|---|---|
| `id` | `String` | Định danh duy nhất | `task_1720000000000` |
| `title` | `String` | Tiêu đề công việc | `"Kiểm tra hệ thống Server Nginx"` |
| `description` | `String` | Mô tả chi tiết | `"Kiểm tra SSL certificate và log lỗi Nginx"` |
| `category` | `String` | Danh mục công việc | `"Server"`, `"Dev"`, `"Học tập"`, `"Công việc"` |
| `deadline` | `String` | Hạn chót hoàn thành | Format ISO Date: `"2026-07-22"` |
| `priority` | `Enum` | Mức độ ưu tiên | `"High"`, `"Medium"`, `"Low"` |
| `completed` | `Boolean` | Trạng thái hoàn thành | `true` / `false` |
| `createdAt` | `String` | Ngày khởi tạo | Format ISO Date: `"2026-07-22"` |

---

### 2.2. ServerStatus (Giám sát máy chủ)
| Field | Type | Description | Constraints / Examples |
|---|---|---|---|
| `id` | `String` | Định danh máy chủ | `"srv_prod_01"` |
| `name` | `String` | Tên máy chủ | `"Production API Gateway"` |
| `ip` | `String` | Địa chỉ IP / Hostname | `"192.168.1.100"` hoặc `"api.aegis.internal"` |
| `status` | `Enum` | Trạng thái máy chủ | `"up"`, `"down"`, `"degraded"` |
| `uptime` | `Number` | Tỷ lệ thời gian hoạt động (%) | `99.98` |
| `latency` | `Number` | Độ độ trễ mạng (ms) | `24` |
| `cpuUsage` | `Number` | Tỷ lệ sử dụng CPU (%) | `42` |
| `memoryUsage` | `Number` | Tỷ lệ sử dụng RAM (%) | `68` |
| `diskUsage` | `Number` | Tỷ lệ dung lượng đĩa (%) | `75` |
| `lastChecked` | `String` | Thời điểm kiểm tra gần nhất | `"16:30:00"` |

---

### 2.3. Notification (Thông báo hệ thống)
| Field | Type | Description | Constraints / Examples |
|---|---|---|---|
| `id` | `String` | Định danh thông báo | `"notif_1720000000000"` |
| `title` | `String` | Tiêu đề thông báo | `"Cảnh báo Server Web-01"` |
| `description` | `String` | Nội dung chi tiết | `"Độ trễ tăng cao trên 250ms"` |
| `category` | `Enum` | Phân loại thông báo | `"task"`, `"server"`, `"system"`, `"news"` |
| `read` | `Boolean` | Đã đọc hay chưa | `true` / `false` |
| `timestamp` | `String` | Thời gian nhận thông báo | `"16:30"` |

---

### 2.4. AssistantConfig (Cấu hình Trợ lý ảo)
| Field | Type | Description | Constraints / Examples |
|---|---|---|---|
| `name` | `String` | Tên trợ lý ảo | Mặc định: `"Aegis"` |
| `prompt` | `String` | System Instruction gốc cho AI | Định hướng cá tính, phong cách trả lời |
| `avatarUrl` | `String` | Ảnh đại diện trợ lý | URL hoặc mã hóa Base64 Data URL |
| `themeColor` | `Enum` | Màu chủ đạo ứng dụng | `"slate"`, `"cyan"`, `"blue"`, `"emerald"`, `"purple"`, `"rose"`, `"amber"` |
| `apiBaseUrl` | `String` | Địa chỉ Backend linh động | e.g. `"http://192.168.1.15:3000"` |

---

## 3. Danh Sách API Endpoints (API Specification)

Tất cả các endpoint sử dụng chuẩn **RESTful JSON HTTP**.

---

### 3.1. Generating AI Daily Briefing
* **Endpoint:** `POST /api/gemini/briefing`
* **Mục đích:** Tạo bản tin tóm tắt đầu ngày thông minh từ dữ liệu Tasks, Servers, Notifications hiện tại của chủ nhân.
* **Headers:** `Content-Type: application/json`
* **Request Body:**
```json
{
  "tasks": [
    {
      "id": "task_1",
      "title": "Kiểm tra Nginx Log",
      "priority": "High",
      "completed": false,
      "deadline": "2026-07-22"
    }
  ],
  "servers": [
    {
      "name": "API Gateway",
      "status": "up",
      "uptime": 99.9,
      "latency": 24
    }
  ],
  "notifications": [
    {
      "title": "Cảnh báo RAM",
      "read": false
    }
  ],
  "assistantName": "Aegis",
  "customPrompt": "Bạn là Aegis, trợ lý ảo cá nhân đa năng..."
}
```

* **Response Success (`200 OK`):**
```json
{
  "text": "### Chào mừng chủ nhân quay trở lại! ☀️\n\nHôm nay hệ thống ghi nhận 1 công việc ưu tiên cao chưa hoàn thành..."
}
```

* **Response Error (`500 Internal Server Error`):**
```json
{
  "error": "Không thể kết nối tới mô hình AI Gemini."
}
```

---

### 3.2. AI Assistant Multi-turn Chatbot
* **Endpoint:** `POST /api/gemini/chat`
* **Mục đích:** Xử lý hội thoại thông minh giữa chủ nhân và Trợ lý AI (có ngữ cảnh realtime về trạng thái server & danh sách công việc).
* **Headers:** `Content-Type: application/json`
* **Request Body:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": "Server nào đang gặp sự cố vậy em?"
    },
    {
      "role": "model",
      "content": "Dạ thưa chủ nhân, hiện tại máy chủ Database-02 đang bị nghẽn RAM ạ."
    },
    {
      "role": "user",
      "content": "Hướng dẫn anh cách giải phóng RAM trên Linux với."
    }
  ],
  "systemInstruction": "Bạn là Aegis, trợ lý ảo cá nhân... Ngữ cảnh Server hiện tại: [...]"
}
```

* **Response Success (`200 OK`):**
```json
{
  "text": "Để giải phóng RAM trên Linux, chủ nhân có thể thực hiện lệnh xóa cache buffer:\n\n```bash\nsudo sync; echo 3 | sudo tee /proc/sys/vm/drop_caches\n```"
}
```

---

### 3.3. AI News & System Health Intelligence Push
* **Endpoint:** `POST /api/gemini/news`
* **Mục đích:** Tổng hợp tin tức công nghệ mới nhất (qua Google Search Grounding) hoặc tổng hợp báo cáo trạng thái hệ thống tự động.
* **Headers:** `Content-Type: application/json`
* **Request Body:**
```json
{
  "topic": "tech-news",
  "customTopic": "Trí tuệ nhân tạo & Android 16",
  "tasks": [],
  "servers": []
}
```

* **Response Success (`200 OK`):**
```json
{
  "news": [
    {
      "id": "notif_1720000000001",
      "title": "Google chính thức ra mắt tính năng AI mới trên Android 16",
      "description": "Bản cập nhật Android 16 tối ưu hóa vi xử lý LTPO và nâng cao hiệu suất AI trên các thiết bị cao cấp.",
      "category": "news",
      "read": false,
      "timestamp": "07:00"
    }
  ]
}
```

---

### 3.4. (Khuyến Nghị) Các Endpoint CRUD Dữ Liệu Chuẩn (Dành cho bản Backend hoàn chỉnh)

Khi xây dựng Database lưu trữ lâu dài (PostgreSQL, MongoDB hoặc SQLite), nên bổ sung các endpoint sau:

| HTTP Method | Route | Description |
|---|---|---|
| `GET` | `/api/tasks` | Lấy danh sách toàn bộ Tasks của User |
| `POST` | `/api/tasks` | Tạo mới một Task |
| `PUT` | `/api/tasks/:id` | Cập nhật thông tin / Trạng thái Task |
| `DELETE` | `/api/tasks/:id` | Xóa một Task |
| `GET` | `/api/servers` | Lấy danh sách trạng thái các máy chủ |
| `POST` | `/api/servers/ping` | Kích hoạt ping kiểm tra sức khỏe máy chủ |
| `GET` | `/api/config` | Lấy cấu hình Trợ lý ảo & Theme |
| `PUT` | `/api/config` | Cập nhật cấu hình Trợ lý ảo & Theme |

---

## 4. Yêu Cầu Kỹ Thuật Cho Backend (Technical Requirements)

### 4.1. Cấu Hính CORS (Cross-Origin Resource Sharing)
Do ứng dụng chạy trên thiết bị di động Android APK thông qua **Capacitor WebView**, các API request sẽ có Origin dạng `capacitor://localhost`, `http://localhost`, hoặc từ các IP mạng nội bộ (LAN IP).

**Yêu cầu cấu hình Header trên Backend:**
```http
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
```

### 4.2. Hỗ Trợ Hủy Tiến Trình Khẩn Cấp (AbortController Signal)
Frontend đã tích hợp cơ chế `AbortController` hủy request ngay lập tức khi người dùng chuyển trang hoặc đổi thao tác.
* Backend nên lắng nghe sự kiện `req.on('close')` để dừng ngay các tiến trình gọi Gemini API đắt đỏ nếu Client đã ngắt kết nối (`Request Aborted`).

### 4.3. Biến Môi Trường (Environment Variables)
Backend cần các biến môi trường sau:
* `PORT`: Cổng chạy HTTP Server (mặc định: `3000`).
* `GEMINI_API_KEY`: API Key lấy từ Google AI Studio (`https://aistudio.google.com/`).
* `DATABASE_URL`: Chuỗi kết nối CSDL (nếu có).

---

## 5. Gợi Ý Công Nghệ Triển Khai Backend (Implementation Stack)

Bạn có thể dễ dàng lập trình Backend này bằng các ngôn ngữ ưa thích:

1. **Node.js (Express / Fastify + `@google/genai` SDK)** *(Rất khuyến nghị — đồng bộ với JavaScript/TypeScript)*
2. **Python (FastAPI / Flask + `google-generativeai`)**
3. **Go (Gin / Fiber + `google.golang.org/genai`)**

---

*Tài liệu được trích xuất tự động từ mã nguồn Aegis Assistant OS.*
