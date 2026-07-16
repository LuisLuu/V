# v_core/domains/orchestration/state_machine.py
import json
import logging
from v_core.domains.orchestration.llm_client import OllamaClient
from v_core.domains.tools.tool_registry import ToolRegistry
from v_core.domains.memory.ram_window import RAMWindow
from v_core.domains.orchestration.sub_agents import RouterNode, ConversationalNode
from v_core.domains.harness.blast_gates import BlastGate
import re

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

        You have access to the following tools: 
        {available_tools}

        CRITICAL RULES OF EXECUTION:
        1. If you need data you do not have, set "Action" to the correct tool_name.
        2. DO NOT hallucinate or guess the tool's output. Wait for the Observation.
        3. If the context contains an "Observation" that answers the user's query, you MUST set "Action" to "None" and put your conclusion in "Final_Answer".

        You MUST output ONLY a valid JSON object. Use this exact format:
        {{
        "Thought": "Your step-by-step reasoning based on the query and any Observations.",
        "Action": "tool_name OR None",
        "Action_Input": {{parameters}},
        "Final_Answer": "Leave empty if calling a tool. If Action is None, put your final response to the user here."
        }}
        """
        
        current_context = f"User Query: {user_query}\n"
        
        for i in range(max_loops):
            try:
                raw_response = self.llm.generate(prompt=current_context, system_prompt=system_prompt)
                
                # CRITICAL: Log exactly what the LLM tried to say so we can debug it
                logging.info(f"[REACT RAW OUTPUT - LOOP {i}]:\n{raw_response}")
                
                # SURGICAL EXTRACTION: Find everything between the first { and last }
                match = re.search(r'\{.*\}', raw_response, re.DOTALL)
                
                if match:
                    json_string = match.group(0)
                    # Add strict=False to prevent crashes from raw newlines
                    parsed = json.loads(json_string, strict=False) 
                else:
                    raise ValueError(f"No valid JSON object found in response.")
                
                action = parsed.get("Action")
                if action and action != "None":
                    # 1. Execute the physical tool
                    tool_output = self.registry.execute_tool(action, parsed.get("Action_Input", {}))
                    
                    # 2. THE RAILGUARD: Hijack the execution flow.
                    # We have the data, so we break the ReAct loop entirely and force a final, natural response.
                    logging.info(f"[ORCHESTRATOR] Railguard triggered. Synthesizing output for {action}.")
                    
                    synthesis_prompt = f"""
                    The user asked: {user_query}
                    You executed the tool '{action}' and received this raw data:
                    {tool_output}
                    
                    Provide the final, natural response to the user based on this data. Do not output JSON.
                    """
                    
                    final_response = self.llm.generate(
                        prompt=synthesis_prompt,
                        system_prompt="You are V. Summarize the system data accurately, directly, and naturally."
                    )
                    
                    return final_response
                else:
                    # No tool needed, return the final answer
                    return str(parsed.get("Final_Answer", "Done."))
                
            except Exception as e:
                logging.error(f"Loop {i} failed: {e}")
                return f"Execution error: {str(e)}"
        
        return "Error: Max cognitive loops reached."