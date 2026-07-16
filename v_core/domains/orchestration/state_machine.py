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
        # Initialize the specialized sub-agents
        self.router = RouterNode(llm_interface=self.llm)
        self.conversationalist = ConversationalNode(llm_interface=self.llm, ram=self.ram)

    def process_prompt(self, user_query: str) -> str:
        """
        The main entry point. Routes the prompt and ensures global memory tracking.
        """
        self.ram.add_interaction(role="user", content=user_query)
        route = self.router.classify_intent(user_query)
        
        if route == "CHAT":
            # We must remove the RAM saving logic inside ConversationalNode now that it's here
            response = self.conversationalist.chat(user_query)
        else:
            response = self.execute_react_loop(user_query=user_query, route=route)
            
        self.ram.add_interaction(role="v", content=response)
        return response

    def execute_react_loop(self, user_query: str = "", route: str = "SYS_EXECUTE", session_id: str | None = None, user_auth: str | None = None, max_loops: int = 5) -> str:
        """
        The isolated ReAct loop. Now accepts optional session variables to support 
        Blast Gate authorization resolutions from chat_routes.py without crashing.
        """
        logging.info(f"[ORCHESTRATOR] Initiating ReAct loop for route: {route}")
        
        # If this is a Blast Gate resolution, handle the pending authorization here
        if session_id and user_auth:
            logging.info(f"[ORCHESTRATOR] Resolving Blast Gate for session {session_id} with auth: {user_auth}")
            if user_auth.upper() == 'Y':
                return "Command Authorized. Resuming execution..."
            else:
                return "Command Blocked by User."

        # Standard ReAct execution parameters
        available_tools = self.registry.get_all_tool_descriptions() 
        
        system_prompt = f"""You are V, an autonomous executing agent. 
Your current operational route is: {route}.
You must evaluate the user query and execute the appropriate tools.
Available Tools: {available_tools}
Format your output exactly as a JSON object with:
"Thought": "your reasoning",
"Action": "tool_name or None",
"Action_Input": {{parameters}},
"Final_Answer": "Your response to the user AS A PLAIN STRING. If Action is 'None', you MUST populate this field."
"""
        
        current_context = f"User Query: {user_query}\n"
        
        for i in range(max_loops):
            try:
                # Fire the cognitive engine
                raw_response = self.llm.generate(prompt=current_context, system_prompt=system_prompt)
                
                # ... [Your JSON parsing and tool registry execution logic goes here] ...
                
                return "Simulated ReAct execution successful based on route." 
                
            except Exception as e:
                logging.error(f"Loop {i} failed: {e}")
                return "System failure during execution."
                
        return "Max cognitive loops reached without final answer."