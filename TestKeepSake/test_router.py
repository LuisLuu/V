import sqlite3
from pathlib import Path
from v_core.domains.memory.sqlite_rom import SQLiteROM
from v_core.domains.memory.router import MemoryRouter

def run_pipeline_test():
    db_path = Path("data/rom.db")
    
    # 1. Initialize the Long-Term Memory (ROM)
    print(">>> Spinning up ROM...")
    rom = SQLiteROM(db_path=str(db_path))
    
    # 2. Injecting V Project specific constraints directly via SQLite to ensure insertion
    print(">>> Injecting hardware specs into memory...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    test_memory = (
        "V Project constraint log: The ESP32-S3 module handles the radio frequency components. "
        "When upgrading the UI capabilities beyond the standard monochrome screen, monitor the GPIO pin "
        "overlap with the RF transceivers to prevent signal degradation."
    )
    
    cursor.execute('''
        INSERT INTO chat_logs (session_id, role, content, tags)
        VALUES ('v_project_test', 'user', ?, 'hardware, esp32-s3')
    ''', (test_memory,))
    conn.commit()
    conn.close()
    
    # 3. Fire the Router (Step 0 Orchestration)
    print("\n>>> Firing MemoryRouter Step 0...")
    router = MemoryRouter(db_path=str(db_path)) 
    
    # Simulate an ambiguous LLM query that requires technical context
    query = "What do I need to watch out for when upgrading the V project screen?"
    
    # *Note: Change '.retrieve_context()' to whatever method name you actually wrote in router.py*
    try:
        retrieved_context = router.evaluate_and_fetch(query) 
        
        print(f"\n[QUERY]: '{query}'")
        print(f"[RETRIEVED CONTEXT]: {retrieved_context}")
        
        # Realist evaluation: Did it actually pull the correct technical details?
        if "radio frequency" in str(retrieved_context).lower():
            print("\n[SUCCESS] Pipeline is green. FTS5 engine routed the technical context perfectly.")
        else:
            print("\n[FAILED] Router fired but missed the critical memory. Check your bm25() ranking logic or stop-word filters.")
            
    except Exception as e:
        print(f"\n[CRASH] The router pipeline failed to execute: {e}")
        print("Evaluate your router.py SQL query. Ensure it targets 'chat_search_idx' and uses the MATCH operator.")

if __name__ == "__main__":
    run_pipeline_test()

    # python -m TestKeepSake.test_router