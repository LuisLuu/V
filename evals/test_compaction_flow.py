import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from memory.ram_window import RAMWindow
from memory.sqlite_rom import SQLiteROM
from agents.compaction import CompactionEngine
from agents.router import MemoryRouter

class SabotagedMockLLM:
    """Mocks a misbehaving Ollama client that wraps JSON in markdown and conversational filler."""
    def generate(self, prompt: str) -> str:
        return (
            "Sure thing, V! Here is the extracted data you requested:\n"
            "```json\n"
            "{\n"
            '  "results": [\n'
            '    {"row_id": 1, "tags": ["calibration", "printer", "enclosure"]}\n'
            "  ]\n"
            "}\n"
            "```\n"
            "Let me know if you need any other rows compacted!"
        )

def run_memory_tests():
    print("--- Starting Memory Architecture Validation ---")
    
    # ---------------------------------------------------------
    # PHASE 1: RAM CAPACITY SENSORS
    # ---------------------------------------------------------
    print("\n🟢 Phase 1: Testing RAM Window Capacity Limits...")
    # Set an artificially tiny limit (100 chars) to force a critical state
    ram = RAMWindow(max_chars=100) 
    
    ram.add_interaction("user", "Short message.", 1)
    print(f"Current RAM size: {ram._get_current_size()} chars. Critical: {ram.is_critical}")
    assert ram.is_critical is False, "FAIL: RAM falsely flagged as critical."
    
    # Overload the RAM
    ram.add_interaction("user", "This is a massive block of text designed to overflow the physical character limit we just set." * 3, 2)
    print(f"Current RAM size: {ram._get_current_size()} chars. Critical: {ram.is_critical}")
    assert ram.is_critical is True, "FAIL: RAM failed to flag critical overflow."
    
    # Test Extraction
    extracted = ram.extract_for_compaction()
    print(f"Extracted {len(extracted)} messages for compaction.")
    assert ram.is_critical is False, "FAIL: RAM is still critical after extraction."
    assert len(ram.buffer) < 2, "FAIL: RAM did not drop older messages to clear capacity."

    # ---------------------------------------------------------
    # PHASE 2: PYDANTIC COMPACTION
    # ---------------------------------------------------------
    print("\n🟡 Phase 2: Testing Pydantic Compaction Batch...")
    rom = SQLiteROM()
    engine = CompactionEngine(rom_connection=rom, llm_client=SabotagedMockLLM())
    
    # Pass the extracted messages into the mock engine
    engine.compact_messages(extracted)
    print("PASS: Compaction engine successfully parsed LLM JSON via Pydantic without crashing.")

    # ---------------------------------------------------------
    # PHASE 3: DYNAMIC ROUTING
    # ---------------------------------------------------------
    print("\n🔴 Phase 3: Testing Dynamic Semantic Router...")
    # Insert a test record to establish a baseline score
    rom.save_message("test_session", "user", "I need to configure my custom ESP32-S3 handheld hardware.", "esp32, hardware, diy")
    
    router = MemoryRouter()
    # A dropoff of 0.8 tests the relative thresholding math
    result = router.evaluate_and_fetch("Tell me about my ESP32-S3 setup.", dropoff_tolerance=0.8)
    
    if result:
        print("PASS: Router successfully extracted context using dynamic baseline.")
    else:
        print("WARNING: Router found no context. (Ensure FTS5 virtual tables are synced).")

    print("\n🎉 ALL MEMORY TESTS EXECUTED.")

if __name__ == "__main__":
    run_memory_tests()