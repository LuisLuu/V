import os
import sys

# Tell Python to look in the parent directory (project root) for modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import sqlite3

# Import your actual memory modules
from v_core.domains.memory.sqlite_rom import SQLiteROM
from v_core.domains.memory.ram_window import RAMWindow
from v_core.domains.memory.compaction import CompactionEngine
from v_core.domains.memory.router import MemoryRouter

class MockLLMClient:
    """A mock LLM to avoid spending API credits during automated testing."""
    def generate(self, prompt: str) -> str:
        # We simulate the exact JSON structure compaction.py expects
        # In a real scenario, the LLM reads the batch. Here, we hardcode the tags we care about.
        return json.dumps({
            "results": [
                {"row_id": 1, "tags": ["omega-77", "constraint", "critical"]},
                {"row_id": 2, "tags": ["noise", "log"]},
                {"row_id": 3, "tags": ["noise", "log"]}
            ]
        })

def run_test():
    test_db_path = "test_rom.db"
    
    print("--- Starting Test 1: Context Pressure & Compaction ---")
    
    # 1. Clean slate
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        print("🧹 Cleared old test database.")

    # 2. Initialize V's modular memory components
    print("🚀 Initializing Memory Modules...")
    rom = SQLiteROM(db_path=test_db_path) # Injecting test DB path
    ram = RAMWindow(capacity=3) # Forcing early threshold
    llm = MockLLMClient()
    compactor = CompactionEngine(rom_connection=rom, llm_client=llm) #
    router = MemoryRouter(db_path=test_db_path) #[cite: 5]

    session_id = "test_session_01"

    # 3. Phase 1: Constraint Injection
    print("\n💉 Injecting Constraint...")
    msg_1 = "Critical constraint: All diagnostic outputs must be tagged with Project ID #OMEGA-77."
    row_1 = rom.save_message(session_id, "user", msg_1) # Save to ROM
    ram.add_interaction("user", msg_1, row_id=row_1) # Track in RAM[cite: 4]
    
    # 4. Phase 2: Context Flooding
    print("🌊 Flooding RAM with noise...")
    for i in range(2):
        noise_msg = f"System log nominal {i}. Nothing to report."
        row_id = rom.save_message(session_id, "system", noise_msg) #[cite: 6]
        ram.add_interaction("system", noise_msg, row_id=row_id) #[cite: 4]

    # 5. Phase 3: Sensor Verification
    print("\n🔍 Checking RAM Sensors...")
    assert ram.is_critical == True, "FAIL: Sensor did not trigger critical status!" #[cite: 4]
    print("✅ PASS: is_critical sensor tripped correctly.")

    # 6. Phase 4: Compaction Execution
    ("⚙️ Executing Compaction Engine...")
    # Extract the oldest messages to compact and reset sensorprint[cite: 4]
    messages_to_compact = ram.extract_for_compaction(count=3) 
    
    # Run the background worker process
    compactor.compact_messages(messages_to_compact)

    assert ram.is_critical == False, "FAIL: RAM did not reset sensor post-extraction." #[cite: 4]
    print("✅ PASS: RAM buffer sliced and reset successfully.")

    # 7. Phase 5: Verification of SQLite ROM tags
    print("\n💾 Verifying Persistent ROM Updates...")
    with sqlite3.connect(test_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tags FROM chat_logs WHERE id = 1")
        tags = cursor.fetchone()[0]
        
    assert "omega-77" in tags, f"FAIL: Tags were not updated in ROM! Found: {tags}"
    print(f"✅ PASS: Row 1 updated with tags via Compaction Engine: [{tags}]") #[cite: 3]

    # 8. Phase 6: Router Recall (Progressive Disclosure)
    print("\n🧠 Testing Router Semantic Recall...")
    # Overriding threshold to 0.0 to account for the small test corpus size
    recalled_context = router.evaluate_and_fetch("omega-77 constraint", threshold=0.0)
    
    assert recalled_context is not None, "FAIL: Router failed to find the compacted memory."
    assert "OMEGA-77" in recalled_context, "FAIL: Recalled context did not contain the constraint."
    print("✅ PASS: Router successfully recalled constraint from ROM.") #[cite: 5]

    print("\n🎉 ALL TESTS PASSED: Compaction flow works perfectly.")

if __name__ == "__main__":
    run_test()