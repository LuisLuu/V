import json
from typing import List, Dict, Any

class CompactionEngine:
    """
    Prevents context rot by structurally moving resolved data from RAM to ROM.
    """
    def __init__(self, rom_connection, llm_client=None):
        self.rom = rom_connection
        self.llm = llm_client

    def _generate_tags(self, content: str) -> str:
        """Generates strict semantic tags using enforced JSON schema."""
        if not self.llm:
            return ""
            
        prompt = (
            "You are a strict data indexing algorithm. Extract 3 to 5 simple, lowercase keywords "
            "from the input text. You must reply ONLY with a valid JSON object containing a single key "
            "'tags' that holds an array of strings.\n\n"
            "Example output format:\n"
            "{\"tags\": [\"keyword1\", \"keyword2\", \"keyword3\"]}\n\n"
            f"Input text: {content}"
        )
        
        try:
            response = self.llm.generate(prompt)
            
            # The model is now forced by the Ollama API to return JSON
            data = json.loads(response)
            tags_list = data.get("tags", [])
            
            # Clean and Validate
            clean_tags = [str(tag).strip().lower() for tag in tags_list if str(tag).strip()]
            
            return ", ".join(clean_tags[:5])
            
        except json.JSONDecodeError:
            print(f"🚨 [LLM ERROR] Model failed to return valid JSON. Raw output: {response}")
            return ""
        except Exception as e:
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
                print(f"🚨 [FATAL COMPACTION ERROR] Failed on row {message.get('row_id')}: {e}")