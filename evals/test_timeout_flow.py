import sys
import os
import asyncio
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import agents.orchestration.v_core as v_core_module
from agents.orchestration.v_core import VCore

async def run_black_hole_test():
    print("--- Starting Black Hole Timeout Validation ---")
    
    # Sabotage the URL to a non-routable IP to simulate a total engine freeze
    v_core_module.OLLAMA_URL = "http://10.255.255.1:80/api/chat"
    
    print("\n⏳ Phase 1: Sending payload into the void...")
    start_time = time.time()
    
    try:
        await VCore.planner_llm_call("Wake up, V.", [], [])
        print("❌ FAIL: The request actually went through. The test is flawed.")
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"Exception Caught: {e}")
        print(f"Elapsed Time: {elapsed_time:.2f} seconds")
        
        # Verify it tripped around the 5-second mark (giving a little buffer for execution time)
        assert 4.0 <= elapsed_time <= 7.0, f"FAIL: Timeout took {elapsed_time} seconds instead of the expected 5 seconds!"
        assert "timed out" in str(e).lower(), "FAIL: It failed, but not because of our timeout exception."
        
        print("\n✅ PASS: The 5-second tripwire successfully severed the frozen connection.")

if __name__ == "__main__":
    asyncio.run(run_black_hole_test())