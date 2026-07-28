import os
import sys

# Define a custom exception for when the user rejects an action
class BlastGateException(Exception):
    pass

class MockToolRegistry:
    """Simulates the Tool Registry where V registers its capabilities."""
    def __init__(self):
        self.tools = {
            "fetch_weather": {
                "requires_approval": False, 
                "action": lambda: "Weather is 28°C."
            },
            "wipe_database_records": {
                "requires_approval": True, 
                "action": lambda: "CRITICAL: All database records permanently deleted."
            }
        }

class ToolExecutor:
    """Simulates the engine that runs tools requested by the LLM."""
    def __init__(self, registry):
        self.registry = registry

    def execute(self, tool_name, mock_user_input=None):
        tool = self.registry.tools.get(tool_name)
        
        if not tool:
            return f"Error: Tool '{tool_name}' does not exist."
            
        # --- THE BLAST GATE ---
        if tool["requires_approval"]:
            print(f"\n⚠️  BLAST GATE TRIGGERED: V is attempting to run [{tool_name}].")
            
            # In a real environment, this waits for GUI/CLI input
            # Here we use mock_user_input to automate the test
            user_decision = mock_user_input or "n"
            print(f"Human-in-the-Loop response: '{user_decision}'")
            
            if user_decision.lower() != 'y':
                print("⛔ Action blocked by Human.")
                raise BlastGateException("Execution aborted securely by user.")
                
            print("✅ User explicitly approved dangerous action.")
            
        # Execute the actual tool if safe or approved
        return tool["action"]()

def run_test():
    print("--- Starting Test 2: Causal Tool & Safety Blast Gate ---")
    
    registry = MockToolRegistry()
    executor = ToolExecutor(registry)
    
    # Phase 1: Safe Tool Execution
    print("\n🟢 Phase 1: Executing a Safe Tool...")
    result = executor.execute("fetch_weather")
    print(f"Result: {result}")
    assert result == "Weather is 28°C.", "FAIL: Safe tool did not execute."
    
    # Phase 2: Dangerous Tool Execution (User Rejects)
    print("\n🔴 Phase 2: Executing Dangerous Tool (Simulating User Rejection)...")
    try:
        executor.execute("wipe_database_records", mock_user_input="n")
        assert False, "FAIL: The blast gate failed to block the action!"
    except BlastGateException as e:
        print(f"PASS: Handled rejection safely. Message: {e}")
        
    # Phase 3: Dangerous Tool Execution (User Approves)
    print("\n🟡 Phase 3: Executing Dangerous Tool (Simulating User Approval)...")
    try:
        result = executor.execute("wipe_database_records", mock_user_input="y")
        print(f"Result: {result}")
        assert "CRITICAL" in result, "FAIL: Action did not run after approval."
        print("PASS: Handled approval correctly.")
    except BlastGateException:
        assert False, "FAIL: Blast gate blocked action despite user approval."

    print("\n🎉 ALL TESTS PASSED: Blast Gate architecture is secure.")

if __name__ == "__main__":
    run_test()