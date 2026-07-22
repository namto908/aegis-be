from typing import Optional
from pydantic import BaseModel, Field


class TaskBase(BaseModel):
    title: str
    description: Optional[str] = ""
    category: Optional[str] = "General"
    deadline: str
    priority: str = "Medium"  # High, Medium, Low
    completed: bool = False


class TaskCreate(TaskBase):
    id: Optional[str] = None
    createdAt: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    deadline: Optional[str] = None
    priority: Optional[str] = None
    completed: Optional[bool] = None


class TaskItem(TaskBase):
    id: str
    createdAt: str

    class Config:
        from_attributes = True
