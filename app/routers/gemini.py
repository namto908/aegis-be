from fastapi import APIRouter, HTTPException, Request, Depends, status
from app.schemas.gemini import (
    BriefingRequest, BriefingResponse,
    ChatRequest, ChatResponse,
    NewsRequest, NewsResponse
)
from app.agent.agent_runtime import agent_runtime

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
        text = await agent_runtime.handle_chat(body)
        return ChatResponse(text=text)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xử lý hội thoại với AI Gemini: {str(e)}"
        )


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
