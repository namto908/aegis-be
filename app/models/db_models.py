from sqlalchemy import Column, String, Boolean, Float, Integer, Text
from app.db import Base


class TaskDB(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    category = Column(String, default="General")
    deadline = Column(String, nullable=False)
    priority = Column(String, default="Medium")  # High, Medium, Low
    completed = Column(Boolean, default=False)
    createdAt = Column(String, nullable=False)


class ServerDB(Base):
    __tablename__ = "servers"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    ip = Column(String, nullable=False)
    status = Column(String, default="up")  # up, down, degraded
    uptime = Column(Float, default=99.9)
    latency = Column(Float, default=20.0)
    cpuUsage = Column(Float, default=30.0)
    memoryUsage = Column(Float, default=50.0)
    diskUsage = Column(Float, default=60.0)
    lastChecked = Column(String, default="")


class NotificationDB(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    category = Column(String, default="system")  # task, server, system, news
    read = Column(Boolean, default=False)
    timestamp = Column(String, nullable=False)


class ConfigDB(Base):
    __tablename__ = "assistant_config"

    id = Column(Integer, primary_key=True, default=1)
    name = Column(String, default="Aegis")
    prompt = Column(Text, default="Bạn là Aegis, trợ lý ảo cá nhân đa năng...")
    avatarUrl = Column(Text, default="")
    themeColor = Column(String, default="cyan")
    apiBaseUrl = Column(String, default="http://localhost:3000")


class ChatMessageDB(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, index=True)
    role = Column(String, nullable=False)  # user, model
    content = Column(Text, default="")
    image = Column(Text, nullable=True)
    file = Column(Text, nullable=True)
    fileName = Column(String, nullable=True)
    thinking = Column(Text, nullable=True)
    timestamp = Column(String, nullable=False)
    created_at = Column(String, nullable=False)


class UserMemoryDB(Base):
    __tablename__ = "user_memories"

    id = Column(String, primary_key=True, index=True)
    category = Column(String, default="preference")  # preference, fact, habit, tech_stack
    key = Column(String, nullable=False)
    value = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)
    updated_at = Column(String, nullable=False)

