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

    def add_interaction(self, role: str, content: str, status: str = "active"):
        """Appends a new message block to the tracking buffer."""
        self.buffer.append({"role": role, "content": content, "status": status})
        self._evaluate_sensor()

    def get_recent_history(self, limit: int = 5) -> str:
        """Formats the latest window slots as a unified string for rapid injection."""
        if not self.buffer:
            return "No previous context."
            
        recent = self.buffer[-limit:]
        return "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in recent])

    def clear_completed(self, condensed_buffer: List[Dict[str, Any]]):
        """Updates the internal state buffer post-compaction pass."""
        self.buffer = condensed_buffer
        self._evaluate_sensor()

    def _evaluate_sensor(self):
        """Monitors working memory bounds to trigger ROM flushes when threshold breaks."""
        if len(self.buffer) >= self.capacity:
            self.is_critical = True
            logging.warning("[RAM WINDOW] Working buffer capacity critical. Compaction required.")
        else:
            self.is_critical = False