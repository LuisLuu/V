# test_rom.py
import logging
from v_core.domains.memory.sqlite_rom import SQLiteROM

# Force logging to print cleanly to your terminal window
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def run_integration_test():
    print("\n--- STARTING ROM VERIFICATION TEST ---\n")
    
    # 1. Initialize DB (Using a temporary file for isolated testing)
    db = SQLiteROM(db_path="test_v_memory.db")
    
    # 2. Test writing data with explicit tags
    print("\n[Action] Writing sample memory logs into database...")
    db.save_message(
        session_id="session_001", 
        role="user", 
        content="Designing a custom structural enclosure for my Bambu A1 3D printer using high-temperature PETG.",
        tags="3dprint,hardware,enclosure"
    )
    
    # 3. Test the Vague Search (Checking if Porter Stemming and Tags work-work)
    print("\n[Action] Testing vague search logic...")
    
    # Search for a word variation ("printing" instead of "3dprint" or "printer")
    search_hits = db.vague_search("printing")
    
    print("\n[Results] Search Output Matrix:")
    for hit in search_hits:
        print(f" -> Found Match ID {hit['id']}: {hit['content']} (Tags: {hit['tags']})")
        
    # 4. Clean up test database file
    import os
    if os.path.exists("test_v_memory.db"):
        os.remove("test_v_memory.db")
        print("\n[Clean] Temporary test database scrubbed from workspace.")
        
    print("\n--- TEST COMPLETE ---")

if __name__ == "__main__":
    run_integration_test()


# python -m TestKeepSake.test_rom