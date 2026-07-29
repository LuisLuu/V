import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, Any
from agents.tools.tool_registry import registry
from agents.tools.preconditions import BaseTool, SecurityTier

# Set up logging for this specific tool
logger = logging.getLogger(__name__)

# FIX: 3 parents, not 4! This points correctly to D:\project-v
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "memory" / "rom.db"

class TaskManagerTool(BaseTool):
    """Handles CRUD operations for V's task list."""
    
    security_tier = SecurityTier.READ  # Upgrade to WRITE/human_approval later if needed
    preconditions = []

    def __init__(self):
        self.name = "task_manager"
        self.description = "Manages user tasks. Can create, read, update, or delete tasks."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string", 
                        "enum": ["create", "read", "update", "delete"],
                        "description": "The CRUD action to perform."
                    },
                    "title": {"type": "string", "description": "Title of the task (required for create)."},
                    "description": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "cancelled"]},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    "task_id": {"type": "integer", "description": "The ID of the task (required for update/delete)."}
                },
                "required": ["action"]
            }
        }

    def execute(self, action: str, title: str | None = None, description: str = "", 
                status: str | None = None, priority: str | None = None, task_id: int | None = None) -> str:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # --- CREATE ---
                if action == "create":
                    if not title:
                        return json.dumps({"status": "failed", "error": "Title is required to create a task."})
                    
                    # Satisfy Python's type checker by using a local string variable
                    safe_priority = priority if priority else "medium"
                    
                    cursor.execute(
                        "INSERT INTO tasks (title, description, priority) VALUES (?, ?, ?)",
                        (title, description, safe_priority)
                    )
                    conn.commit()
                    return json.dumps({"status": "success", "message": f"Task '{title}' created with ID {cursor.lastrowid}."})

                # --- READ ---
                elif action == "read":
                    cursor.execute("SELECT id, title, description, status, priority FROM tasks WHERE status != 'completed'")
                    rows = [dict(row) for row in cursor.fetchall()]
                    if not rows:
                        return json.dumps({"status": "success", "message": "No active tasks found."})
                    return json.dumps({"status": "success", "tasks": rows})

                # --- UPDATE ---
                elif action == "update":
                    if not task_id:
                        return json.dumps({"status": "failed", "error": "task_id integer is required for update."})
                    
                    updates = []
                    params = []
                    if status:
                        updates.append("status = ?")
                        params.append(status)
                    if priority:
                        updates.append("priority = ?")
                        params.append(priority)
                        
                    if not updates:
                        return json.dumps({"status": "failed", "error": "Nothing to update."})
                        
                    params.append(task_id)
                    query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
                    
                    cursor.execute(query, tuple(params))
                    conn.commit()
                    
                    if cursor.rowcount == 0:
                        return json.dumps({"status": "failed", "error": f"Task ID {task_id} not found."})
                    return json.dumps({"status": "success", "message": f"Task {task_id} updated successfully."})

                # --- DELETE ---
                elif action == "delete":
                    if not task_id:
                        return json.dumps({"status": "failed", "error": "task_id integer is required for delete."})
                        
                    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                    conn.commit()
                    
                    if cursor.rowcount == 0:
                        return json.dumps({"status": "failed", "error": f"Task ID {task_id} not found. Deletion failed."})
                    return json.dumps({"status": "success", "message": f"Task {task_id} deleted permanently."})

                else:
                    return json.dumps({"status": "failed", "error": f"Unknown action: {action}"})

        except sqlite3.Error as e:
            logger.error(f"SQL Crash during '{action}': {str(e)}", exc_info=True)
            return json.dumps({"status": "failed", "error": f"Database error: {str(e)}"})
            
        except Exception as e:
            logger.error(f"Unexpected Python crash in task_manager: {str(e)}", exc_info=True)
            return json.dumps({"status": "failed", "error": f"System crash: {str(e)}"})
            
        # Catch-all return to completely silence the "must return value on all paths" error
        return json.dumps({"status": "failed", "error": "Unexpected execution path."})
# Register the tool
registry.register_tool("task_manager", TaskManagerTool())