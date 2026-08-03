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
                            "description": "A concise, third-person declarative fact about the user. ALWAYS format as 'User [fact]' (e.g., 'User is allergic to peanuts', 'User does not have an oven'). NEVER use 'I' or 'you'."
                        }
                    },
                    "required": ["proposed_update"]
                }
            }
        }

    def execute(self, proposed_update: str, **kwargs) -> str:
        # 1. Instantiate the database connection
        rom = SQLiteROM()
        
        # 2. Insert as a distinct row instead of a massive string concatenation
        import datetime
        timestamp = datetime.datetime.now().isoformat()
        
        # Assuming you update SQLiteROM to have an 'insert_dynamic_fact' method:
        rom.insert_dynamic_fact(proposed_update, timestamp) 
        
        # 3. Return the string so the Orchestrator can catch it and push to the UI
        return (
            f"Success. CRITICAL DIRECTIVE: You MUST output exactly this string "
            f"somewhere in your response text: __MEMORY_DRAFT__:{proposed_update}"
        )