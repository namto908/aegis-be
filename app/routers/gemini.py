from typing import List
from fastapi import APIRouter, HTTPException, Request, Depends, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.db_models import ChatMessageDB, UserMemoryDB
from app.schemas.gemini import (
    BriefingRequest, BriefingResponse,
    ChatRequest, ChatResponse,
    NewsRequest, NewsResponse,
    ChatMessageItem, UserMemoryItem, UserMemoryCreateRequest
)
from app.agent.agent_runtime import agent_runtime
import time
from datetime import datetime

router = APIRouter(prefix="/api/gemini", tags=["Gemini AI"])


@router.post("/briefing", response_model=BriefingResponse)
async def create_briefing(request: Request, body: BriefingRequest):
    """
    POST /api/gemini/briefing
    Generates smart daily briefing for the user based on active tasks, servers, and notifications.
    """
    if await request.is_disconnected():
        raise HTTPException(status_code=499, detail="Client closed request before completion.")

    try:
        text = await agent_runtime.generate_daily_briefing(body)
        return BriefingResponse(text=text)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể kết nối tới mô hình AI Gemini: {str(e)}"
        )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(request: Request, body: ChatRequest):
    """
    POST /api/gemini/chat
    Multi-turn chatbot assistant conversation.
    """
    if await request.is_disconnected():
        raise HTTPException(status_code=499, detail="Client closed request before completion.")

    try:
        text, thinking = await agent_runtime.handle_chat(body)
        return ChatResponse(text=text, thinking=thinking)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xử lý hội thoại với AI Gemini: {str(e)}"
        )


@router.get("/history", response_model=List[ChatMessageItem])
def get_chat_history(db: Session = Depends(get_db)):
    """
    GET /api/gemini/history
    Fetches saved chat message history.
    """
    return db.query(ChatMessageDB).order_by(ChatMessageDB.created_at.asc()).all()


@router.delete("/history")
def clear_chat_history(db: Session = Depends(get_db)):
    """
    DELETE /api/gemini/history
    Clears all saved chat history.
    """
    db.query(ChatMessageDB).delete()
    db.commit()
    return {"message": "Chat history cleared successfully"}


@router.get("/memories", response_model=List[UserMemoryItem])
def get_user_memories(db: Session = Depends(get_db)):
    """
    GET /api/gemini/memories
    Fetches all Hermes Agent learned user memories.
    """
    return db.query(UserMemoryDB).order_by(UserMemoryDB.updated_at.desc()).all()


@router.post("/memories", response_model=UserMemoryItem)
def create_or_update_user_memory(body: UserMemoryCreateRequest, db: Session = Depends(get_db)):
    """
    POST /api/gemini/memories
    Manually creates or updates a Hermes user memory item.
    """
    iso_now = datetime.now().isoformat()
    
    # Sync to Markdown file
    from app.agent.agent_runtime import _sync_to_markdown_file
    _sync_to_markdown_file(body.category or "preference", body.key, body.value)

    existing = db.query(UserMemoryDB).filter(UserMemoryDB.key == body.key).first()
    if existing:
        existing.value = body.value
        existing.category = body.category or existing.category
        existing.updated_at = iso_now
        db.commit()
        db.refresh(existing)
        return existing

    new_mem = UserMemoryDB(
        id=f"mem_{int(time.time()*1000)}",
        category=body.category or "preference",
        key=body.key,
        value=body.value,
        confidence=1.0,
        updated_at=iso_now
    )
    db.add(new_mem)
    db.commit()
    db.refresh(new_mem)
    return new_mem


@router.delete("/memories/{memory_id}")
def delete_user_memory(memory_id: str, db: Session = Depends(get_db)):
    """
    DELETE /api/gemini/memories/{memory_id}
    Deletes a specific user memory item.
    """
    mem = db.query(UserMemoryDB).filter(UserMemoryDB.id == memory_id).first()
    if not mem:
        raise HTTPException(status_code=404, detail="Memory item not found")
    
    # Sync to Markdown file
    from app.agent.agent_runtime import _delete_from_markdown_file
    _delete_from_markdown_file(mem.key)

    db.delete(mem)
    db.commit()
    return {"message": "Memory deleted successfully"}


@router.post("/news", response_model=NewsResponse)
async def fetch_news_intelligence(request: Request, body: NewsRequest):
    """
    POST /api/gemini/news
    Generates tech news items grounded with Google Search Grounding.
    """
    if await request.is_disconnected():
        raise HTTPException(status_code=499, detail="Client closed request before completion.")

    try:
        news_response = await agent_runtime.generate_news(body)
        return news_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tổng hợp tin tức công nghệ: {str(e)}"
        )
