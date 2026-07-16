# v_core/domains/memory/ram_window.py
import logging

class RAMWindow:
    """
    Manages V's short-term memory buffer. 
    Uses a computational sensor to flag when compaction is required.
    """
    def __init__(self, capacity: int = 10):
        # Capacity limits how many interactions we keep in RAM before compacting
        self.capacity = capacity
        self.buffer = []
        self.is_critical = False

    def add_interaction(self, role: str, content: str, status: str = "active"):
        """Appends a new message to the RAM buffer with a status tag."""
        self.buffer.append({"role": role, "content": content, "status": status})
        self._evaluate_sensor()

    def get_recent_history(self, limit: int = 5) -> str:
        """Retrieves the most recent interactions formatted as a string."""
        if not self.buffer:
            return "No previous context."
            
        recent = self.buffer[-limit:]
        history_str = ""
        for msg in recent:
            history_str += f"{msg['role'].upper()}: {msg['content']}\n"
        return history_str.strip()

    def _evaluate_sensor(self):
        """Computational sensor that triggers when the RAM window is full."""
        if len(self.buffer) >= self.capacity:
            self.is_critical = True
            logging.warning("[RAM WINDOW] Capacity critical. Compaction trigger required.")
        else:
            self.is_critical = False