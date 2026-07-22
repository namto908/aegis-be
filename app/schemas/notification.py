from typing import Optional
from pydantic import BaseModel, Field


class NotificationBase(BaseModel):
    title: str
    description: str = ""
    category: str = "system"  # task, server, system, news
    read: bool = False
    timestamp: str


class NotificationCreate(NotificationBase):
    id: Optional[str] = None


class NotificationItem(NotificationBase):
    id: str

    class Config:
        from_attributes = True
