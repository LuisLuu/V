from typing import List, Dict, Any

class CompactionEngine:
    """
    Prevents context rot by structurally moving resolved data from RAM to ROM.
    """
    def __init__(self, rom_connection, llm_client=None):
        self.rom = rom_connection
        self.llm = llm_client

    def _generate_tags(self, content: str) -> str:
        """Helper to generate semantic search tags via local LLM before writing to ROM."""
        if not self.llm:
            return ""
        prompt = (
            f"Extract 3 to 5 simple, lowercase, comma-separated keywords or broad concepts "
            f"from this text for database indexing. Return ONLY the keywords:\n\n{content}\n"
        )
        try:
            response = self.llm.generate(prompt)
            return response.strip().replace(" ", "").lower()
        except Exception:
            return ""

    def compact_messages(self, messages_to_compact: List[Dict[str, Any]]):
        """
        Background worker process. Generates tags and updates existing ROM records via row_id.
        """
        if not self.llm:
            return

        for message in messages_to_compact:
            tags = self._generate_tags(message["content"])
            if tags:
                self.rom.update_tags(row_id=message["row_id"], tags=tags)