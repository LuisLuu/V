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
            # Constructive fix: Split by comma, strip whitespace properly, and rejoin.
            # This preserves spaces inside multi-word concepts.
            clean_tags = [tag.strip().lower() for tag in response.split(",")]
            return ", ".join(clean_tags)
            
        except Exception as e:
            # STOP SWALLOWING ERRORS. Print exactly why the LLM failed.
            print(f"🚨 [LLM ERROR] Tag generation failed: {e}")
            return ""

    def compact_messages(self, messages_to_compact: List[Dict[str, Any]]):
        """
        Background worker process. Generates tags and updates existing ROM records via row_id.
        """
        if not self.llm:
            print("⚠️ [COMPACTION] No LLM client provided. Aborting compaction.")
            return

        print(f"⚙️ [COMPACTION] Starting worker for {len(messages_to_compact)} messages...")

        for message in messages_to_compact:
            try:
                # Ensure row_id actually exists in the payload to prevent silent KeyErrors
                row_id = message.get("row_id")
                if not row_id:
                    print(f"⚠️ [COMPACTION] Missing row_id for message: {message.get('content', '')[:20]}...")
                    continue
                
                tags = self._generate_tags(message["content"])
                
                if tags:
                    self.rom.update_tags(row_id=row_id, tags=tags)
                    print(f"✅ [COMPACTION] Row {row_id} updated with tags: [{tags}]")
                else:
                    print(f"⚠️ [COMPACTION] Skipped Row {row_id}: No tags generated.")
                    
            except Exception as e:
                # If SQLite is locked or the pipeline crashes, you will now see it.
                print(f"🚨 [FATAL COMPACTION ERROR] Failed on row {message.get('row_id')}: {e}")