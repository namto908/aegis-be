from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from app.schemas.task import TaskItem
from app.schemas.server import ServerStatusItem
from app.schemas.notification import NotificationItem


class BriefingTaskInput(BaseModel):
    id: Optional[str] = None
    title: str
    priority: Optional[str] = "Medium"
    completed: Optional[bool] = False
    deadline: Optional[str] = ""


class BriefingServerInput(BaseModel):
    name: str
    status: Optional[str] = "up"
    uptime: Optional[float] = 99.9
    latency: Optional[float] = 20.0


class BriefingNotifInput(BaseModel):
    title: str
    read: Optional[bool] = False


class BriefingRequest(BaseModel):
    tasks: Optional[List[Dict[str, Any]]] = []
    servers: Optional[List[Dict[str, Any]]] = []
    notifications: Optional[List[Dict[str, Any]]] = []
    assistantName: Optional[str] = "Aegis"
    customPrompt: Optional[str] = ""


class BriefingResponse(BaseModel):
    text: str


class ChatMessage(BaseModel):
    role: str  # "user" or "model" or "assistant"
    content: str
    image: Optional[str] = None
    file: Optional[str] = None
    fileName: Optional[str] = None
    thinking: Optional[str] = None


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    systemInstruction: Optional[str] = None


class ChatResponse(BaseModel):
    text: str
    thinking: Optional[str] = None


class NewsRequest(BaseModel):
    topic: Optional[str] = "tech-news"
    customTopic: Optional[str] = ""
    tasks: Optional[List[Dict[str, Any]]] = []
    servers: Optional[List[Dict[str, Any]]] = []


class NewsResponse(BaseModel):
    news: List[NotificationItem] = []
    title: Optional[str] = None
    description: Optional[str] = None
    contentDetail: Optional[str] = None
    sourceUrl: Optional[str] = None


class ChatMessageItem(BaseModel):
    id: str
    role: str
    content: str
    image: Optional[str] = None
    file: Optional[str] = None
    fileName: Optional[str] = None
    thinking: Optional[str] = None
    timestamp: str
    created_at: str


class UserMemoryItem(BaseModel):
    id: str
    category: str
    key: str
    value: str
    confidence: float
    updated_at: str


class UserMemoryCreateRequest(BaseModel):
    category: Optional[str] = "preference"
    key: str
    value: str

