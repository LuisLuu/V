import requests
import time
import sqlite3
import sys
from pathlib import Path
import time


SESSION_ID = f"v-diagnostic-run-{int(time.time())}"

BASE_DIR = Path(__file__).resolve().parent.parent 
DB_PATH = BASE_DIR / "data" / "rom.db"

# --- CONFIGURATION ---
# Adjust this URL if your FastAPI router is mounted differently in main.py
API_URL = "http://localhost:8000/api/chat/"
SESSION_ID = "v-diagnostic-run-001"
TOTAL_MESSAGES = 12

def run_api_stress_test():

    print(f"🚀 [STAGE 1] Initiating API Stress Test for Session: {SESSION_ID}")
    
    for i in range(1, TOTAL_MESSAGES + 1):
        payload = {
            "message": f"This is test message number {i}. Remember this.",
            "session_id": SESSION_ID
        }
        
        try:
            start_time = time.time()
            response = requests.post(API_URL, json=payload)
            latency = time.time() - start_time
            
            if response.status_code == 200:
                print(f"  ✅ Msg {i:02d} | Latency: {latency:.2f}s | Status: OK")
            else:
                print(f"  ❌ Msg {i:02d} | FAILED | Code: {response.status_code}")
                print(f"     Details: {response.text}")
                sys.exit(1)
                
        except requests.exceptions.ConnectionError:
            print("\n🚨 ERROR: Could not connect to the API. Is your FastAPI server running?")
            sys.exit(1)

def autopsy_database():
    print("\n⏳ [STAGE 2] Waiting 5 seconds for background CompactionEngine to finish...")
    time.sleep(5)
    
    print("\n🔍 [STAGE 3] Running SQLite DB Autopsy...")
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, role, tags FROM chat_logs WHERE session_id = ? ORDER BY id ASC", 
            (SESSION_ID,)
        )
        rows = cursor.fetchall()
        
        total_rows = len(rows)
        print(f"  📊 Total Rows Found: {total_rows} (Expected: {TOTAL_MESSAGES * 2})")
        
        if total_rows != (TOTAL_MESSAGES * 2):
            print("  ❌ FATAL: Row count mismatch. You likely have a data duplication bug.")
            return

        # RAM Window Capacity is 10 (5 user/assistant pairs). 
        # Over 12 messages (24 rows), the engine triggers compaction.
        # This results in 16 compacted rows and 8 active RAM rows.
        compacted_rows = rows[:16]
        active_ram_rows = rows[16:]
        
        print("\n  [Compaction Check - Oldest 16 Rows]")
        all_compacted_have_tags = True
        for row in compacted_rows:
            if not row["tags"]:
                all_compacted_have_tags = False
                print(f"    ❌ Row {row['id']} ({row['role']}) is MISSING tags!")
            else:
                print(f"    ✅ Row {row['id']} ({row['role']}) has tags: [{row['tags']}]")
                
        print("\n  [Active RAM Check - Newest 8 Rows]")
        all_active_are_empty = True
        for row in active_ram_rows:
            if row["tags"]:
                all_active_are_empty = False
                print(f"    ❌ Row {row['id']} ({row['role']}) incorrectly has tags before being sliced: [{row['tags']}]")
                
        print("\n🏁 --- DIAGNOSTIC RESULTS ---")
        if all_compacted_have_tags and all_active_are_empty and total_rows == (TOTAL_MESSAGES * 2):
            print("🟢 ALL SYSTEMS NOMINAL. The RAM window, background compaction, and DB row_id updates are working flawlessly.")
        else:
            print("🔴 TEST FAILED. Check the logs above to see where the pipeline broke down.")
            
    except Exception as e:
        print(f"🚨 DB Error: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_api_stress_test()
    autopsy_database()