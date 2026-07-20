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

    def compact_context(self, session_id: str, active_ram: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sweeps the active RAM buffer.
        Flushes completed turns into FTS5 SQLite storage and retains open steps in RAM.
        """
        condensed_ram = []
        for message in active_ram:
            if message.get("status") == "completed":
                # Extract tags automatically right before disk allocation
                tags = self._generate_tags(message["content"])
                
                # Aligning directly with SQLiteROM interface
                self.rom.save_message(
                    session_id=session_id,
                    role=message["role"],
                    content=message["content"],
                    tags=tags
                )
            else:
                # Retain unresolved tasks or immediate dependencies in short-term RAM
                condensed_ram.append(message)
                
        return condensed_ram