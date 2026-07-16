# v_core/domains/orchestration/state_machine.py
import json
import logging
from v_core.domains.orchestration.llm_client import OllamaClient
from v_core.domains.tools.tool_registry import ToolRegistry
from v_core.domains.memory.ram_window import RAMWindow
from v_core.domains.orchestration.sub_agents import RouterNode, ConversationalNode
from v_core.domains.harness.blast_gates import BlastGate

class Orchestrator:
    def __init__(self):
        self.llm = OllamaClient()
        self.registry = ToolRegistry()
        self.blast_gate = BlastGate()
        self.ram = RAMWindow()
        self.router = RouterNode(llm_interface=self.llm)
        self.conversationalist = ConversationalNode(llm_interface=self.llm, ram=self.ram)

    def process_prompt(self, user_query: str) -> str:
        self.ram.add_interaction(role="user", content=user_query)
        route = self.router.classify_intent(user_query)
        
        if route == "CHAT":
            response = self.conversationalist.chat(user_query)
        else:
            response = self.execute_react_loop(user_query=user_query, route=route)
            
        self.ram.add_interaction(role="v", content=response)
        return response

    def execute_react_loop(self, user_query: str = "", route: str = "SYS_EXECUTE", 
                           session_id: str | None = None, user_auth: str | None = None, 
                           max_loops: int = 5) -> str:
        logging.info(f"[ORCHESTRATOR] Initiating ReAct loop for route: {route}")
        
        if session_id and user_auth:
            return "Command Authorized." if user_auth.upper() == 'Y' else "Command Blocked by User."

        context_history = self.ram.get_recent_history(limit=5)
        available_tools = self.registry.get_all_tool_descriptions() 
        
        system_prompt = f"""You are V, an autonomous executing agent. 
Your current operational route is: {route}.
Previous Conversation Context:
{context_history}

You must evaluate the user query and execute the appropriate tools.
Available Tools: {available_tools}
Format your output exactly as a JSON object with:
"Thought": "your reasoning",
"Action": "tool_name or None",
"Action_Input": {{parameters}},
"Final_Answer": "Your response to the user AS A PLAIN STRING."
"""
        
        current_context = f"User Query: {user_query}\n"
        
        for i in range(max_loops):
            try:
                raw_response = self.llm.generate(prompt=current_context, system_prompt=system_prompt)
                parsed = json.loads(raw_response.strip().replace('```json', '').replace('```', ''))
                
                action = parsed.get("Action")
                if action and action != "None":
                    tool_output = self.registry.execute_tool(action, parsed.get("Action_Input", {}))
                    current_context += f"\nObservation: {str(tool_output)}"
                else:
                    return str(parsed.get("Final_Answer", "Done."))
                
            except Exception as e:
                logging.error(f"Loop {i} failed: {e}")
                return f"Execution error: {str(e)}"
        
        return "Error: Max cognitive loops reached."