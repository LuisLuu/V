import difflib
from datetime import datetime

from agents.tools.preconditions import BaseTool
from memory.sqlite_rom import SQLiteROM


class MemoryDraftTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.description = "Draft a new long-term memory, user preference, or core behavioral rule."

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "draft_memory_update",
                "description": (
                    "Draft a new long-term memory, user preference, or core behavioral rule to save "
                    "in the system ROM. Use this ONLY for persistent facts (e.g., 'User prefers Python', "
                    "'Always explain code step-by-step'). DO NOT use this for temporary states, current tasks, "
                    "or conversational filler."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "proposed_update": {
                            "type": "string",
                            "description": (
                                "A concise, third-person declarative fact about the user. "
                                "ALWAYS format as 'User [fact]' (e.g., 'User is allergic to peanuts', "
                                "'User does not have an oven'). NEVER use 'I' or 'you'."
                            ),
                        }
                    },
                    "required": ["proposed_update"],
                },
            },
        }

    def execute(self, proposed_update: str, **kwargs) -> str:
        rom = SQLiteROM()

        # 1. Fetch raw learned facts string from ROM
        raw_facts_str = rom.get_learned_facts()

        # 2. Extract clean individual fact strings if DB is not empty
        existing_facts = []
        if raw_facts_str and "No dynamic facts learned yet" not in raw_facts_str:
            for line in raw_facts_str.split("\n"):
                clean_line = line.lstrip("- ").strip().lower()
                if clean_line:
                    existing_facts.append(clean_line)

        # 3. Deduplication check via SequenceMatcher ratio
        proposed_clean = proposed_update.lower().strip()
        similarity_threshold = 0.80  # 80% similarity match threshold

        for fact in existing_facts:
            similarity = difflib.SequenceMatcher(
                None, proposed_clean, fact
            ).ratio()
            if similarity >= similarity_threshold:
                return (
                    f"System Notification: Fact '{proposed_update}' already exists in memory "
                    f"as '{fact}'. Update skipped to prevent duplication."
                )

        # 4. Save distinct new memory row
        timestamp = datetime.now().isoformat()
        rom.insert_dynamic_fact(proposed_update, timestamp)

        return (
            f"Success. CRITICAL DIRECTIVE: You MUST output exactly this string "
            f"somewhere in your response text: __MEMORY_DRAFT__:{proposed_update}"
        )