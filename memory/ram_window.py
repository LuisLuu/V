import logging
from typing import List, Dict, Any

class RAMWindow:
    """
    Manages V's short-term working memory buffer.
    Flags when buffer capacity constraints require a compaction pass.
    """
    def __init__(self, capacity: int = 10):
        self.capacity = capacity
        self.buffer: List[Dict[str, Any]] = []
        self.is_critical = False

    def add_interaction(self, role: str, content: str, row_id: int | None, status: str = "active"):
        """Appends a new message block, now tracking the DB row_id."""
        self.buffer.append({
            "role": role, 
            "content": content, 
            "row_id": row_id, 
            "status": status
        })
        self._evaluate_sensor()

    def get_recent_history(self, limit: int = 5) -> str:
        """Formats the latest window slots as a unified string for rapid injection."""
        if not self.buffer:
            return "No previous context."
            
        recent = self.buffer[-limit:]
        return "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in recent])

    def extract_for_compaction(self, count: int = 4) -> List[Dict[str, Any]]:
        """
        Instantly slices the oldest messages out of RAM to prevent race conditions.
        Returns the sliced messages for the background worker and resets the critical flag.
        """
        if not self.buffer:
            return []
            
        # Grab the oldest N messages
        to_compact = self.buffer[:count]
        
        # Keep the rest in active memory
        self.buffer = self.buffer[count:]
        self.is_critical = False
        
        return to_compact

    def _evaluate_sensor(self):
        """Monitors working memory bounds to trigger ROM flushes when threshold breaks."""
        if len(self.buffer) >= self.capacity:
            self.is_critical = True
            logging.warning("[RAM WINDOW] Working buffer capacity critical. Compaction required.")
        else:
            self.is_critical = False