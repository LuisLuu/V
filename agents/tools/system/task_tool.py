from typing import Any, Dict
from agents.tools.preconditions import BaseTool, SecurityTier
from agents.tools.system.task_agent import TaskAgent

class TaskManagerTool(BaseTool):
    name: str = "task_manager"
    description: str = "Create, read, update, or delete tasks in V's system ledger."
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
                            "enum": ["create", "list", "read", "update", "delete"],
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
                        "deadline": {
                            "type": "string",
                            "description": "Optional deadline in ISO 8601 format (e.g., '2026-07-28T17:00:00')."
                        },
                        "task_id": {
                            "type": "integer",
                            "description": "Task ID (required for 'update' or 'delete'). If the user refers to a task by name or pronoun (e.g., 'that task'), you MUST deduce the ID by cross-referencing the chat history with the [CURRENT SYSTEM TASKS] list."
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed", "cancelled"],
                            "description": "Task status (required for 'update', optional for 'list')."
                        },
                        # --- CRITICAL FIX: The Authorization Flag ---
                        "authorized": {
                            "type": "boolean",
                            "description": "Set to true ONLY if the user has explicitly granted permission for this action in the recent chat history. Defaults to false."
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
                priority=kwargs.get("priority", "medium"),
                deadline=kwargs.get("deadline")
            )
        # FIX: Map both 'list' and 'read' to the same function to prevent strict routing failures
        elif action in ["list", "read"]:
            return self.agent.list_tasks(status_filter=kwargs.get("status"))
        elif action == "update":
            task_id = kwargs.get("task_id")
            status = kwargs.get("status")
            if task_id is None or status is None:
                return {"status": "error", "message": "'task_id' and 'status' are required for 'update'."}
            return self.agent.update_task(task_id=task_id, status=status)
        # FIX: Execute the new delete logic
        elif action == "delete":
            task_id = kwargs.get("task_id")
            if task_id is None:
                return {"status": "error", "message": "'task_id' is required for 'delete'."}
            return self.agent.delete_task(task_id=task_id)
        else:
            return {"status": "error", "message": f"Unknown action '{action}'."}