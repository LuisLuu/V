import sqlite3
from typing import Optional
from agents.tools.preconditions import BaseTool, SecurityTier

class TaskManagerTool(BaseTool):
    security_tier = SecurityTier.WRITE
    preconditions = []

    def __init__(self, db_path="memory/rom.db"):
        self.name = "task_manager"
        self.description = "Manages the user's task list (create, read, update, complete, delete)."
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS tasks (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            task TEXT NOT NULL,
                            priority TEXT DEFAULT 'medium',
                            status TEXT DEFAULT 'pending'
                        )''')

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["create", "read", "update", "complete", "delete"]},
                    "task": {"type": "string", "description": "The task description."},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    "task_id": {"type": "integer", "description": "Required for update, complete, or delete."},
                    "filter_status": {"type": "string", "enum": ["pending", "completed", "all"], "description": "Used with 'read' to filter tasks."}
                },
                "required": ["action"]
            }
        }

    def execute(
        self, 
        action: str, 
        task: Optional[str] = None, 
        priority: str = "medium", 
        task_id: Optional[int] = None, 
        filter_status: str = "pending"
    ) -> str:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if action == "create":
                if not task:
                    return "Error: task text required for creation."
                cursor.execute("INSERT INTO tasks (task, priority, status) VALUES (?, ?, 'pending')", (task, priority))
                return f"Task created successfully with ID {cursor.lastrowid}."
            
            elif action == "read":
                if filter_status == "all":
                    cursor.execute("SELECT id, task, priority, status FROM tasks")
                else:
                    cursor.execute("SELECT id, task, priority, status FROM tasks WHERE status = ?", (filter_status,))
                tasks = cursor.fetchall()
                if not tasks:
                    return f"No {filter_status} tasks found."
                return "Tasks: " + ", ".join([f"[ID: {t[0]}] {t[1]} ({t[2]}) - {t[3]}" for t in tasks])
            
            elif action == "update":
                if not task_id or not task: 
                    return "Error: task_id and task text required for update."
                cursor.execute("UPDATE tasks SET task = ?, priority = ? WHERE id = ?", (task, priority, task_id))
                return f"Task {task_id} updated."

            elif action == "complete":
                if not task_id: 
                    return "Error: task_id required to complete a task."
                cursor.execute("UPDATE tasks SET status = 'completed' WHERE id = ?", (task_id,))
                if cursor.rowcount == 0: 
                    return f"Error: Task ID {task_id} not found."
                return f"Task {task_id} marked as completed and archived."
            
            elif action == "delete":
                if not task_id: 
                    return "Error: task_id required for deletion."
                cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                if cursor.rowcount == 0: 
                    return f"Error: Task ID {task_id} not found."
                return f"Task {task_id} permanently deleted."
            
            else:
                return f"Error: Invalid action '{action}' requested."