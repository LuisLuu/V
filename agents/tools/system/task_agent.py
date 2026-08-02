import logging
from typing import Dict, Any, List, Optional
from memory.sqlite_rom import SQLiteROM
logger = logging.getLogger("v_core.tools.task_agent")

class TaskAgent:
    """
    Executes synchronous CRUD operations directly into the ROM database 'tasks' table.
    Bypasses RAM and Compaction layers completely.
    """
    def __init__(self, rom: SQLiteROM | None = None):
        self.rom = rom if rom else SQLiteROM()

    def create_task(self, title: str, description: str = "", priority: str = "medium", deadline: Optional[str] = None) -> Dict[str, Any]:
        """Writes a new task to ROM, now supporting deadlines."""
        try:
            with self.rom._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO tasks (title, description, priority, deadline) VALUES (?, ?, ?, ?)",
                    (title, description, priority, deadline)
                )
                task_id = cursor.lastrowid
                conn.commit()
                
            logger.info(f"Task Created: [{task_id}] {title} | Due: {deadline}")
            return {"status": "success", "task_id": task_id, "message": f"Task '{title}' added."}
        except Exception as e:
            logger.error(f"Task creation failed: {e}")
            return {"status": "error", "message": str(e)}
        
    def list_tasks(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Queries the active tasks ledger, enforcing priority ordering."""
        query = "SELECT id, title, status, priority, deadline FROM tasks"
        params = ()
        
        if status_filter:
            query += " WHERE status = ?"
            params = (status_filter,)
                        
        query += " ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END, created_at DESC"
            
        with self.rom._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def update_task(self, status: str, task_id: Optional[int] = None, title: Optional[str] = None) -> Dict[str, Any]:
        """Modifies a task's state safely using either exact ID or constrained title match."""
        valid_statuses = ['pending', 'in_progress', 'completed', 'cancelled']
        if status not in valid_statuses:
            return {"status": "error", "message": f"Invalid state. Must be one of {valid_statuses}."}
            
        if not task_id and not title:
            return {"status": "error", "message": "Must provide either task_id or title to update."}

        try:
            with self.rom._get_connection() as conn:
                cursor = conn.cursor()
                
                # Direct ID target
                if task_id is not None:
                    cursor.execute(
                        "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (status, task_id)
                    )
                    target_id = task_id
                else:
                    # Safe Title Resolution: Verify matching records first
                    cursor.execute("SELECT id FROM tasks WHERE title LIKE ?", (f"%{title}%",))
                    matches = cursor.fetchall()
                    
                    if len(matches) == 0:
                        return {"status": "error", "message": f"No task found matching '{title}'."}
                    elif len(matches) > 1:
                        return {
                            "status": "error", 
                            "message": f"Multiple tasks match '{title}'. Please specify the exact task_id."
                        }
                    
                    target_id = matches[0]["id"]
                    cursor.execute(
                        "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (status, target_id)
                    )

                conn.commit()
                
            logger.info(f"Task {target_id} updated to {status}.")
            # THE FIX: Inject the exact ID into the return payload
            return {"status": "success", "message": f"[SYSTEM NOTIFICATION]: Task ID {target_id} successfully marked as {status}. Inform the user."}
        except Exception as e:
            logger.error(f"Task update failed: {e}")
            return {"status": "error", "message": str(e)}

    def delete_task(self, task_id: Optional[int] = None, title: Optional[str] = None) -> Dict[str, Any]:
        """Permanently removes a single task safely using either exact ID or single title match."""
        if not task_id and not title:
            return {"status": "error", "message": "Must provide either task_id or title to delete."}

        try:
            with self.rom._get_connection() as conn:
                cursor = conn.cursor()
                
                # Direct ID target
                if task_id is not None:
                    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                    target_id = task_id # <--- ADD THIS LINE to prevent UnboundLocalError
                else:
                    # Safe Title Resolution: Verify matching records first
                    cursor.execute("SELECT id FROM tasks WHERE title LIKE ?", (f"%{title}%",))
                    matches = cursor.fetchall()
                    
                    if len(matches) == 0:
                        return {"status": "error", "message": f"No task found matching '{title}'."}
                    elif len(matches) > 1:
                        return {
                            "status": "error", 
                            "message": f"Multiple tasks match '{title}'. Please specify the exact task_id to delete."
                        }
                    
                    target_id = matches[0]["id"]
                    cursor.execute("DELETE FROM tasks WHERE id = ?", (target_id,))
                
                affected = cursor.rowcount
                conn.commit()
                
            if affected == 0:
                return {"status": "error", "message": f"Task {target_id} missing or already deleted."}
                
            logger.info(f"Task {target_id} deleted.")
            
            # <--- THE FIX: Loud System Notification --->
            return {"status": "success", "message": f"[SYSTEM NOTIFICATION]: Task ID {target_id} successfully deleted from the ledger. Inform the user."}

        except Exception as e:
            logger.error(f"Task deletion failed: {e}")
            return {"status": "error", "message": str(e)}