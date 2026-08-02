from typing import Any, Dict
from agents.tools.preconditions import BaseTool, SecurityTier
from agents.tools.system.task_agent import TaskAgent

class TaskManagerTool(BaseTool):
    name: str = "task_manager"
    description: str = "Create, read, update, or delete tasks in V's system ledger."
    security_tier: SecurityTier = SecurityTier.READ

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
                            "description": "The task action to perform. CRITICAL TRANSLATION RULES:\n"
                                           "- If the user says 'done', 'finished', 'completed', 'already did', or 'remove from list', you MUST use action='update' with status='completed'.\n"
                                           "- NEVER use action='delete' unless the user explicitly tells you to permanently wipe or destroy a task from the database.\n"
                                           "- To find finished or archived tasks, use 'list' with status='completed'."
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
                            "description": "Task status (required for 'update'). Use 'completed' when listing tasks to retrieve the historical archive."
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
        result = None
        if action == "create":
            title = kwargs.get("title")
            if not title:
                raise ValueError("'title' is required for 'create' action.")
            result = self.agent.create_task(
                title=title,
                description=kwargs.get("description", ""),
                priority=kwargs.get("priority", "medium"),
                deadline=kwargs.get("deadline")
            )
        elif action in ["list", "read"]:
            return self.agent.list_tasks(status_filter=kwargs.get("status"))
        elif action == "update":
            task_id = kwargs.get("task_id")
            title = kwargs.get("title")
            status = kwargs.get("status")
            if status is None:
                raise ValueError("'status' is required for 'update'.")
            if task_id is None and title is None:
                raise ValueError("Either 'task_id' or 'title' is required to update.")
            
            result = self.agent.update_task(status=status, task_id=task_id, title=title)

        elif action == "delete":
            task_id = kwargs.get("task_id")
            title = kwargs.get("title")
            if task_id is None and title is None:
                raise ValueError("Either 'task_id' or 'title' is required for 'delete'.")
            
            result = self.agent.delete_task(task_id=task_id, title=title)

        # --- THE ERROR INTERCEPTOR FIX ---
        if isinstance(result, dict) and result.get("status") == "error":
            raise RuntimeError(result.get("message", "Task operation failed."))
            
        return result