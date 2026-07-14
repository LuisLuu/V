# test_agent.py
import json
from v_core.domains.orchestration.state_machine import Orchestrator

class MockLLM:
    """
    A simulated brain that outputs perfectly formatted JSON 
    to test the Orchestrator's ReAct loop and Blast Gates.
    """
    def __init__(self):
        self.step = 0

    def generate(self, prompt: str) -> str:
        self.step += 1
        print(f"\n[MOCK LLM] Generating Step {self.step}...")
        
        if self.step == 1:
            # Step 1: A safe READ operation. The Blast Gate should auto-approve this.
            return json.dumps({
                "Thought": "I need to scan the root directory to see what files exist.",
                "Action": "directory_scanner",
                "Action_Input": {"directory_path": "."}
            })
        elif self.step == 2:
            # Step 2: A dangerous WRITE operation. The Blast Gate MUST intercept this.
            return json.dumps({
                "Thought": "Now I will execute a terminal command to prove I can interact with the OS.",
                "Action": "command_executor",
                "Action_Input": {"command": "echo V is officially online."}
            })
        else:
            # Step 3: The termination phase.
            return json.dumps({
                "Thought": "All tools tested successfully. I will report back to the user.",
                "Action": "None",
                "Action_Input": {},
                "Final_Answer": "Test complete. My FileSystem and System Terminal tools are fully operational."
            })

def run_live_test():
    print("--- BOOTING V'S COGNITIVE CORE ---")
    
    # 1. Initialize the simulated brain and the Orchestrator
    dummy_brain = MockLLM()
    agent = Orchestrator(llm_interface=dummy_brain)

    query = "Test your tools and security gates."
    print(f"User: {query}")

    # 2. Fire the first ReAct loop
    result = agent.execute_react_loop(user_query=query)
    
    # 3. Handle the Security Intercept
    if result.startswith("SESSION:"):
        print(f"\n🛑 [SYSTEM INTERCEPT] Blast Gate Triggered!")
        
        # Extract the hidden session ID and the visible UI prompt
        parts = result.split("|", 1)
        session_id = parts[0].split(":")[1]
        ui_prompt = parts[1]
        
        print(ui_prompt)
        
        # 4. The Human-in-the-Loop physical authorization
        user_auth = input("\nType 'Y' to authorize, or 'N' to block: ")
        
        # 5. Resume the state machine with the exact cached memory
        print("\n--- RESUMING COGNITIVE LOOP ---")
        final_result = agent.execute_react_loop(session_id=session_id, user_auth=user_auth)
        print(f"\nFinal Agent Output:\n{final_result}")
    else:
        print(f"\nFinal Agent Output:\n{result}")

if __name__ == "__main__":
    run_live_test()