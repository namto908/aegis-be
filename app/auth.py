import logging
from typing import Optional
import httpx
from fastapi import Header, HTTPException, Depends, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.db_models import UserDB, ConfigDB

logger = logging.getLogger(__name__)

async def verify_google_token(token: str) -> dict:
    """
    Verifies a Google ID token by making a call to Google's tokeninfo API.
    Supports a mock bypass for development/testing: 'mock_user_token_<name>_<email_slug>'.
    """
    if token.startswith("mock_user_token_"):
        parts = token.split("_")
        name = parts[3] if len(parts) > 3 else "Mock User"
        email = parts[4] if len(parts) > 4 else "mockuser@example.com"
        user_id = f"google_mock_{email.replace('@', '_').replace('.', '_')}"
        return {
            "id": user_id,
            "email": email,
            "name": name,
            "picture": "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150"
        }
    
    # Standard Google Token Verification via HTTP endpoint
    url = f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=5.0)
            if response.status_code != 200:
                logger.error(f"Google token verification failed with status {response.status_code}: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token xác thực Google không hợp lệ hoặc đã hết hạn."
                )
            
            data = response.json()
            if "error_description" in data:
                logger.error(f"Google token verification returned error: {data['error_description']}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token xác thực Google không hợp lệ."
                )
            
            return {
                "id": data["sub"],
                "email": data["email"],
                "name": data.get("name", data["email"].split("@")[0]),
                "picture": data.get("picture")
            }
        except httpx.RequestError as e:
            logger.error(f"Network error verifying Google token: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Không thể kết nối đến máy chủ xác thực của Google."
            )

async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> UserDB:
    """
    FastAPI dependency to extract and verify the bearer token, returning the current DB user.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thiếu token xác thực hoặc định dạng không đúng. Yêu cầu đăng nhập."
        )
    
    token = authorization.split("Bearer ")[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token xác thực rỗng."
        )
    
    user_info = await verify_google_token(token)
    
    user = db.query(UserDB).filter(UserDB.id == user_info["id"]).first()
    if not user:
        logger.info(f"Creating new user in DB: {user_info['email']} ({user_info['id']})")
        user = UserDB(
            id=user_info["id"],
            email=user_info["email"],
            name=user_info["name"],
            picture=user_info["picture"]
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Initialize config for this user
        cfg = db.query(ConfigDB).filter(ConfigDB.user_id == user.id).first()
        if not cfg:
            logger.info(f"Initializing default assistant config for new user {user.email}")
            from app.config import settings
            cfg = ConfigDB(
                user_id=user.id,
                name="Aegis",
                prompt="Bạn là Aegis, trợ lý ảo cá nhân đa năng rành công nghệ, tính cách lôi cuốn, tinh tế và luôn đặt bảo mật lên hàng đầu. Hãy trả lời ngắn gọn, thiết thực, có cấu trúc sử dụng Markdown nhẹ bằng Tiếng Việt.",
                avatarUrl="",
                themeColor="slate",
                apiBaseUrl=""
            )
            db.add(cfg)
            db.commit()
            
    return user
