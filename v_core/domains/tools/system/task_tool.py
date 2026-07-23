from typing import Any, Dict
from v_core.domains.tools.preconditions import BaseTool, SecurityTier
from v_core.domains.tools.system.task_agent import TaskAgent

class TaskManagerTool(BaseTool):
    name: str = "task_manager"
    description: str = "Create, list, or update tasks in V's system ledger."
    security_tier: SecurityTier = SecurityTier.WRITE

    def __init__(self, agent: TaskAgent | None = None):
        self.agent = agent if agent else TaskAgent()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["create", "list", "update"],
                            "description": "The task action to perform."
                        },
                        "title": {
                            "type": "string",
                            "description": "Task title (required for 'create')."
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed task description (optional)."
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "Task priority level (default: medium)."
                        },
                        "task_id": {
                            "type": "integer",
                            "description": "Task ID (required for 'update')."
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed", "cancelled"],
                            "description": "Task status (required for 'update', optional filter for 'list')."
                        }
                    },
                    "required": ["action"]
                }
            }
        }

    def execute(self, action: str, **kwargs) -> Any:
        if action == "create":
            title = kwargs.get("title")
            if not title:
                return {"status": "error", "message": "'title' is required for 'create' action."}
            return self.agent.create_task(
                title=title,
                description=kwargs.get("description", ""),
                priority=kwargs.get("priority", "medium")
            )
        elif action == "list":
            return self.agent.list_tasks(status_filter=kwargs.get("status"))
        elif action == "update":
            task_id = kwargs.get("task_id")
            status = kwargs.get("status")
            if task_id is None or status is None:
                return {"status": "error", "message": "'task_id' and 'status' are required for 'update'."}
            return self.agent.update_task(task_id=task_id, status=status)
        else:
            return {"status": "error", "message": f"Unknown action '{action}'."}