from typing import Optional
from pydantic import BaseModel, Field


class AssistantConfigSchema(BaseModel):
    name: str = "Aegis"
    prompt: str = "Bạn là Aegis, trợ lý ảo cá nhân..."
    avatarUrl: Optional[str] = ""
    themeColor: str = "cyan"
    apiBaseUrl: str = "http://localhost:25530"

    class Config:
        from_attributes = True
