import time
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.db_models import NotificationDB, UserDB
from app.auth import get_current_user
from app.schemas.notification import NotificationItem, NotificationCreate

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationItem])
def get_all_notifications(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """GET /api/notifications - Get all notifications for current user"""
    return db.query(NotificationDB).filter(NotificationDB.user_id == current_user.id).all()


@router.post("", response_model=NotificationItem, status_code=status.HTTP_201_CREATED)
def create_notification(
    notif_in: NotificationCreate,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """POST /api/notifications - Create notification (idempotent by id, since the
    frontend's sync effect can occasionally re-fire and POST the same freshly-created
    notification twice before its id is reflected back into local state)."""
    notif_id = notif_in.id or f"notif_{int(time.time() * 1000)}"

    existing = db.query(NotificationDB).filter(
        NotificationDB.id == notif_id,
        NotificationDB.user_id == current_user.id
    ).first()
    if existing:
        return existing

    db_notif = NotificationDB(
        id=notif_id,
        user_id=current_user.id,
        title=notif_in.title,
        description=notif_in.description or "",
        category=notif_in.category or "system",
        read=notif_in.read,
        timestamp=notif_in.timestamp or time.strftime("%H:%M")
    )
    db.add(db_notif)
    db.commit()
    db.refresh(db_notif)
    return db_notif


@router.put("/{notif_id}/read", response_model=NotificationItem)
def mark_notification_read(
    notif_id: str,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """PUT /api/notifications/{notif_id}/read - Mark notification as read"""
    db_notif = db.query(NotificationDB).filter(
        NotificationDB.id == notif_id,
        NotificationDB.user_id == current_user.id
    ).first()
    if not db_notif:
        raise HTTPException(status_code=404, detail=f"Notification with ID {notif_id} not found")

    db_notif.read = True
    db.commit()
    db.refresh(db_notif)
    return db_notif


@router.delete("/{notif_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notif_id: str,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """DELETE /api/notifications/{notif_id} - Delete notification"""
    db_notif = db.query(NotificationDB).filter(
        NotificationDB.id == notif_id,
        NotificationDB.user_id == current_user.id
    ).first()
    if not db_notif:
        raise HTTPException(status_code=404, detail=f"Notification with ID {notif_id} not found")

    db.delete(db_notif)
    db.commit()
    return None
