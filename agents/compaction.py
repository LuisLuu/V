import json
from typing import List, Dict, Any
import re

class CompactionEngine:
    """
    Prevents context rot by structurally moving resolved data from RAM to ROM via batch inference.
    """
    def __init__(self, rom_connection, llm_client=None):
        self.rom = rom_connection
        self.llm = llm_client

    def compact_messages(self, messages_to_compact: List[Dict[str, Any]]):
        """
        Background worker process. Generates tags for an entire batch of messages in one LLM call.
        """
        if not self.llm:
            print("⚠️ [COMPACTION] No LLM client provided. Aborting compaction.")
            return

        # Filter out any malformed messages to prevent payload errors
        valid_messages = [m for m in messages_to_compact if m.get("row_id")]
        if not valid_messages:
            return

        print(f"⚙️ [COMPACTION] Starting BATCH worker for {len(valid_messages)} messages...")

        # 1. Structure the input payload for the LLM
        batch_payload = [{"row_id": m["row_id"], "content": m["content"]} for m in valid_messages]

        prompt = (
            "You are a strict data indexing and summarization algorithm.\n"
            "Task 1: Write a concise, 1-2 sentence summary of the overall conversation narrative in this batch.\n"
            "Task 2: Extract 3 to 5 simple, lowercase keywords for each input text.\n"
            "You must reply ONLY with a valid JSON object. Format:\n"
            "{\n"
            "  \"summary\": \"<insert 1-2 sentence summary here>\",\n"
            "  \"results\": [{\"row_id\": 1, \"tags\": [\"keyword1\", \"keyword2\"]}]\n"
            "}\n\n"
            f"CRITICAL RULE: The 'results' array MUST contain exactly {len(valid_messages)} objects. Do not skip any row.\n\n"
            f"Batch inputs: {json.dumps(batch_payload)}"
        )

        try:
            # 2. Single API Call handles all messages at once
            response = self.llm.generate(prompt)
            
            # --- NEW: JSON Extraction & Self-Healing ---
            clean_response = response.strip()
            
            # Strip markdown formatting if the LLM includes it
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            elif clean_response.startswith("```"):
                clean_response = clean_response[3:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
                
            # Regex to forcefully isolate the JSON object from conversational filler
            json_match = re.search(r'\{.*\}', clean_response, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON object found in LLM response.")
                
            clean_response = json_match.group(0)
            # -------------------------------------------

            # 3. Parse the batched response and route to Database
            data = json.loads(clean_response)
            
            rolling_summary = data.get("summary", "")
            
            for item in data.get("results", []):
                row_id = item.get("row_id")
                raw_tags = item.get("tags", [])
                
                if not row_id or not isinstance(raw_tags, list):
                    continue
                    
                # Clean and Validate
                clean_tags = [str(tag).strip().lower() for tag in raw_tags if str(tag).strip()]
                tags_str = ", ".join(clean_tags[:5])
                
                if tags_str:
                    self.rom.update_tags(row_id=row_id, tags=tags_str)
                    print(f"✅ [COMPACTION] Row {row_id} updated with tags: [{tags_str}]")
                else:
                    print(f"⚠️ [COMPACTION] Skipped Row {row_id}: No tags generated.")
            
            return rolling_summary
                    
        except json.JSONDecodeError as e:
            print(f"🚨 [LLM ERROR] Batch failed to return valid JSON. Error: {e} | Raw output: {response}")
            return ""
        except ValueError as ve:
            print(f"🚨 [EXTRACTION ERROR] {ve} | Raw output: {response}")
            return ""
        except Exception as e:
            print(f"🚨 [FATAL COMPACTION ERROR] Batch processing failed: {e}")
            return ""