import time
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.db_models import TaskDB, UserDB
from app.auth import get_current_user
from app.schemas.task import TaskItem, TaskCreate, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.get("", response_model=List[TaskItem])
def get_all_tasks(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """GET /api/tasks - Retrieve all tasks for current user"""
    tasks = db.query(TaskDB).filter(TaskDB.user_id == current_user.id).all()
    return tasks


@router.post("", response_model=TaskItem, status_code=status.HTTP_201_CREATED)
def create_task(
    task_in: TaskCreate,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """POST /api/tasks - Create a new task"""
    task_id = task_in.id or f"task_{int(time.time() * 1000)}"
    created_at = task_in.createdAt or time.strftime("%Y-%m-%d")

    db_task = TaskDB(
        id=task_id,
        user_id=current_user.id,
        title=task_in.title,
        description=task_in.description or "",
        category=task_in.category or "General",
        deadline=task_in.deadline,
        priority=task_in.priority or "Medium",
        completed=task_in.completed,
        createdAt=created_at
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


@router.put("/{task_id}", response_model=TaskItem)
def update_task(
    task_id: str,
    task_in: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """PUT /api/tasks/{task_id} - Update task details or completed status"""
    db_task = db.query(TaskDB).filter(
        TaskDB.id == task_id,
        TaskDB.user_id == current_user.id
    ).first()
    if not db_task:
        raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found")

    update_data = task_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        if val is not None:
            setattr(db_task, field, val)

    db.commit()
    db.refresh(db_task)
    return db_task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """DELETE /api/tasks/{task_id} - Delete a task"""
    db_task = db.query(TaskDB).filter(
        TaskDB.id == task_id,
        TaskDB.user_id == current_user.id
    ).first()
    if not db_task:
        raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found")

    db.delete(db_task)
    db.commit()
    return None
