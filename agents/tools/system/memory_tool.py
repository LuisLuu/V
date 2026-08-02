from agents.tools.preconditions import BaseTool
from memory.sqlite_rom import SQLiteROM  # Pull in the ROM

class MemoryDraftTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.description = "Draft a new long-term memory, user preference, or core behavioral rule."

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "draft_memory_update",
                "description": "Draft a new long-term memory, user preference, or core behavioral rule to save in the system ROM. Use this ONLY for persistent facts (e.g., 'User prefers Python', 'Always explain code step-by-step'). DO NOT use this for temporary states, current tasks, or conversational filler.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "proposed_update": {
                            "type": "string",
                            "description": "The concise, declarative statement to add to the user's Behavioral Context."
                        }
                    },
                    "required": ["proposed_update"]
                }
            }
        }

    def execute(self, proposed_update: str, **kwargs) -> str:
        # 1. Instantiate the database connection
        rom = SQLiteROM()
        
        # 2. Fetch, append, and save
        current_facts = rom.get_learned_facts()
        updated_facts = current_facts + f"\n- {proposed_update}" if current_facts else f"- {proposed_update}"
        rom.update_learned_facts(updated_facts)
        
        # 3. Return the string so the Orchestrator can catch it and push to the UI
        return (
            f"Success. CRITICAL DIRECTIVE: You MUST output exactly this string "
            f"somewhere in your response text: __MEMORY_DRAFT__:{proposed_update}"
        )