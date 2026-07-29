import logging
from typing import List, Dict, Any

class RAMWindow:
    """
    Manages V's short-term working memory using a dynamic, token-aware buffer
    instead of a rigid message count.
    """
    def __init__(self, max_chars: int = 4000): # ~1000 tokens, adjust based on your LLM
        self.max_chars = max_chars
        self.buffer: List[Dict[str, Any]] = []
        self.is_critical = False

    def _get_current_size(self) -> int:
        """Fast proxy for token counting."""
        return sum(len(str(msg.get("content", ""))) for msg in self.buffer)

    def add_interaction(self, role: str, content: str, row_id: int | None, status: str = "active"):
        self.buffer.append({
            "role": role, 
            "content": content, 
            "row_id": row_id, 
            "status": status
        })
        self._evaluate_sensor()

    def get_recent_history(self) -> str:
        if not self.buffer:
            return "No previous context."
        return "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in self.buffer])

    def extract_for_compaction(self) -> List[Dict[str, Any]]:
        """
        Slices the oldest messages out of RAM until the buffer is safely 
        under 75% of its maximum capacity.
        """
        if not self.buffer:
            return []
            
        to_compact = []
        target_size = self.max_chars * 0.75
        
        # Pop oldest messages dynamically until the physical text size drops below threshold
        while self.buffer and self._get_current_size() > target_size:
            to_compact.append(self.buffer.pop(0))
            
        self.is_critical = False
        return to_compact

    def _evaluate_sensor(self):
        """Monitors working memory bounds using actual character weight."""
        current_size = self._get_current_size()
        if current_size >= self.max_chars:
            self.is_critical = True
            logging.warning(f"[RAM WINDOW] Buffer capacity critical ({current_size} chars). Compaction required.")
        else:
            self.is_critical = False