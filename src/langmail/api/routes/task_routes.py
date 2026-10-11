"""PersonalMail AI — Task Routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from langmail.services import TaskService

router = APIRouter(prefix="/api", tags=["tasks"])


class TaskStatusUpdate(BaseModel):
    status: str  # 'pending' or 'completed'


class TaskCreateRequest(BaseModel):
    title: str
    deadline: Optional[str] = None
    priority: str = "medium"
    source_from: Optional[str] = None
    source_text: Optional[str] = None
    thread_id: Optional[str] = None
    message_id: Optional[str] = None


@router.get("/tasks")
def list_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
):
    """List all extracted tasks and deadlines with optional filters."""
    tasks = TaskService.list_tasks(status=status, priority=priority, search=search)
    return {"tasks": tasks, "count": len(tasks)}


@router.post("/tasks")
def create_task(req: TaskCreateRequest):
    """Manually create an action item or deadline."""
    task = TaskService.create_task(
        title=req.title,
        thread_id=req.thread_id,
        message_id=req.message_id,
        deadline=req.deadline,
        priority=req.priority,
        source_from=req.source_from,
        source_text=req.source_text,
    )
    return task


@router.patch("/tasks/{task_id}")
def update_task_status(task_id: str, req: TaskStatusUpdate):
    """Mark a task pending or completed."""
    updated = TaskService.update_task_status(task_id, req.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str):
    """Delete a task."""
    success = TaskService.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted", "id": task_id}
