import logging
from typing import Any, Dict, List


class RAMWindow:
    """Manages working memory bounds and compaction slicing for the RAM window[cite: 20]."""

    def __init__(self, max_chars: int = 4000):
        self.max_chars = max_chars
        self.buffer = []
        self.rolling_summary = "No previous context."
        self.is_critical = False

    def get_recent_history(self) -> str:
        # Drop the permanent rolling_summary injection. Let MemoryRouter handle recall[cite: 20].
        if not self.buffer:
            return "No previous context."

        history_text = "\n".join(
            [
                f"{msg['role'].upper()}: {msg['content']}"
                for msg in self.buffer
            ]
        )
        return history_text

    def _get_current_size(self) -> int:
        """Fast proxy for token counting[cite: 20]."""
        return sum(len(str(msg.get("content", ""))) for msg in self.buffer)

    def add_interaction(
        self,
        role: str,
        content: str,
        row_id: int | None,
        status: str = "active",
    ):
        self.buffer.append(
            {
                "role": role,
                "content": content,
                "row_id": row_id,
                "status": status,
            }
        )
        self._evaluate_sensor()

    def extract_for_compaction(self) -> List[Dict[str, Any]]:
        """Slices the oldest messages out of RAM until the buffer is safely

        under 75% of its maximum capacity[cite: 20].
        """
        if not self.buffer:
            return []

        to_compact = []
        target_size = self.max_chars * 0.75

        # Pop oldest messages dynamically until the physical text size drops below threshold[cite: 20]
        while self.buffer and self._get_current_size() > target_size:
            to_compact.append(self.buffer.pop(0))

        self.is_critical = False
        return to_compact

    def _evaluate_sensor(self):
        """Monitors working memory bounds using actual character weight[cite: 20]."""
        current_size = self._get_current_size()
        if current_size >= self.max_chars:
            self.is_critical = True
            logging.warning(
                f"[RAM WINDOW] Buffer capacity critical ({current_size} chars). Compaction required."
            )
        else:
            self.is_critical = False

    def update_summary(self, new_summary: str):
        """Appends the newly generated compaction summary to the rolling summary[cite: 20]."""
        if not new_summary:
            return

        if self.rolling_summary == "No previous context.":
            self.rolling_summary = new_summary
        else:
            self.rolling_summary += f" {new_summary}"

        # Optional: Keep the summary from ballooning infinitely[cite: 20]
        if len(self.rolling_summary) > 1000:
            # Simple truncation to keep only the most recent summary info[cite: 20]
            self.rolling_summary = "..." + self.rolling_summary[-997:]