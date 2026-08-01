import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.orchestration.state_machine import execute_tool_async
from agents.tools.tool_registry import registry
from agents.tools.system.command_executor import CommandExecutor

async def run_live_ammo_tests():
    print("--- Starting Live Ammo Pipeline Validation ---")
    
    # Ensure the command executor is registered
    if not registry.has_tool("command_executor"):
        registry.register_tool("command_executor", CommandExecutor())

    # --- THE FIX: Bypass Causal Sensors for the test ---
    # The sensor correctly detected Docker was off and blocked execution early.
    # We clear the preconditions here so the payload reaches the Blast Gate.
    executor = registry.get_tool("command_executor")
    assert executor is not None, "CRITICAL: command_executor not found in registry!"
    executor.preconditions = []
    
    print("\n💥 Phase 1: Firing Destructive Command into the State Machine...")
    
    # We hit the actual execution pipeline, not just the gate logic
    result = await execute_tool_async("command_executor", {"command": "rm -rf /logs"})
    
    print(f"Pipeline Interception Result: {result}")
    
    assert result["status"] == "HITL_REQUIRED", "FAIL: State machine bypassed the Blast Gate!"
    assert "AUTHORIZATION REQUIRED" in result.get("error", ""), "FAIL: UI prompt was stripped from the pipeline."
    
    print("\n✅ PASS: The State Machine successfully intercepted the live round and requested HITL authorization.")

if __name__ == "__main__":
    asyncio.run(run_live_ammo_tests())