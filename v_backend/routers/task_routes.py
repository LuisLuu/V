from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from v_core.domains.tools.system.task_agent import TaskAgent

task_router = APIRouter(prefix="/api/tasks", tags=["tasks"])
agent = TaskAgent()

class CreateTaskRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    priority: Optional[str] = "medium"

class UpdateTaskRequest(BaseModel):
    status: str

@task_router.post("/")
def create_task(payload: CreateTaskRequest):
    res = agent.create_task(
        title=payload.title,
        description=payload.description or "",
        priority=payload.priority or "medium"
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@task_router.get("/")
def list_tasks(status: Optional[str] = None) -> List[Dict[str, Any]]:
    return agent.list_tasks(status_filter=status)

@task_router.patch("/{task_id}")
def update_task(task_id: int, payload: UpdateTaskRequest):
    res = agent.update_task(task_id=task_id, status=payload.status)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res