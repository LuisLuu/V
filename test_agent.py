# test_agent.py
from v_core.domains.orchestration.state_machine import Orchestrator
from v_core.domains.orchestration.llm_client import OllamaClient

def run_live_test():
    print("--- BOOTING V'S COGNITIVE CORE (LIVE LLM) ---")
    
    # 1. Initialize the REAL brain
    live_brain = OllamaClient(model_name="llama3") 
    agent = Orchestrator(llm_interface=live_brain)

    # 2. Issue a real command requiring tool usage
    query = "Look at the current directory using your scanner tool and tell me what files are here."
    print(f"User: {query}")

    # 3. Fire the ReAct loop
    result = agent.execute_react_loop(user_query=query)
    
    # 4. Handle Security Intercepts (if she goes rogue)
    if result.startswith("SESSION:"):
        print(f"\n🛑 [SYSTEM INTERCEPT] Blast Gate Triggered!")
        parts = result.split("|", 1)
        session_id = parts[0].split(":")[1]
        ui_prompt = parts[1]
        
        print(ui_prompt)
        user_auth = input("\nType 'Y' to authorize, or 'N' to block: ")
        
        print("\n--- RESUMING COGNITIVE LOOP ---")
        final_result = agent.execute_react_loop(session_id=session_id, user_auth=user_auth)
        print(f"\nFinal Agent Output:\n{final_result}")
    else:
        print(f"\nFinal Agent Output:\n{result}")

if __name__ == "__main__":
    run_live_test()