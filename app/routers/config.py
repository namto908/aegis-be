from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.db_models import ConfigDB, UserDB
from app.auth import get_current_user
from app.schemas.config import AssistantConfigSchema

router = APIRouter(prefix="/api/config", tags=["Assistant Config"])


def _get_or_create_config(db: Session, user: UserDB) -> ConfigDB:
    cfg = db.query(ConfigDB).filter(ConfigDB.user_id == user.id).first()
    if not cfg:
        from app.config import settings
        cfg = ConfigDB(
            user_id=user.id,
            name="Aegis",
            prompt="Bạn là Aegis, trợ lý ảo cá nhân đa năng rành công nghệ, tính cách lôi cuốn, tinh tế và luôn đặt bảo mật lên hàng đầu. Hãy trả lời ngắn gọn, thiết thực, có cấu trúc sử dụng Markdown nhẹ bằng Tiếng Việt.",
            avatarUrl="",
            themeColor="slate",
            apiBaseUrl=f"http://localhost:{settings.port}"
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.get("", response_model=AssistantConfigSchema)
def get_assistant_config(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """GET /api/config - Get assistant configuration for current user"""
    return _get_or_create_config(db, current_user)


@router.put("", response_model=AssistantConfigSchema)
def update_assistant_config(
    cfg_in: AssistantConfigSchema,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """PUT /api/config - Update assistant configuration for current user"""
    cfg = _get_or_create_config(db, current_user)
    
    cfg.name = cfg_in.name
    cfg.prompt = cfg_in.prompt
    cfg.avatarUrl = cfg_in.avatarUrl or ""
    cfg.themeColor = cfg_in.themeColor
    cfg.apiBaseUrl = cfg_in.apiBaseUrl

    db.commit()
    db.refresh(cfg)
    return cfg
