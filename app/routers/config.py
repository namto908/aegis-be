from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.db_models import ConfigDB
from app.schemas.config import AssistantConfigSchema

router = APIRouter(prefix="/api/config", tags=["Assistant Config"])


def _get_or_create_config(db: Session) -> ConfigDB:
    cfg = db.query(ConfigDB).filter(ConfigDB.id == 1).first()
    if not cfg:
        cfg = ConfigDB(
            id=1,
            name="Aegis",
            prompt="Bạn là Aegis, trợ lý ảo cá nhân...",
            avatarUrl="",
            themeColor="cyan",
            apiBaseUrl="http://localhost:3000"
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.get("", response_model=AssistantConfigSchema)
def get_assistant_config(db: Session = Depends(get_db)):
    """GET /api/config - Get assistant configuration"""
    return _get_or_create_config(db)


@router.put("", response_model=AssistantConfigSchema)
def update_assistant_config(cfg_in: AssistantConfigSchema, db: Session = Depends(get_db)):
    """PUT /api/config - Update assistant configuration"""
    cfg = _get_or_create_config(db)
    
    cfg.name = cfg_in.name
    cfg.prompt = cfg_in.prompt
    cfg.avatarUrl = cfg_in.avatarUrl or ""
    cfg.themeColor = cfg_in.themeColor
    cfg.apiBaseUrl = cfg_in.apiBaseUrl

    db.commit()
    db.refresh(cfg)
    return cfg
