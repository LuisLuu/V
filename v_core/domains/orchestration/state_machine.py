# v_core/domains/orchestration/state_machine.py
import json
import re
import uuid
from v_core.domains.tools.tool_registry import ToolRegistry
from v_core.domains.harness.blast_gates import BlastGate
from typing import Optional

class Orchestrator:
    """
    The central ReAct engine. Hardened with JSON structural enforcement, 
    memory compression, and HITL state caching.
    """
    def __init__(self, llm_interface):
        self.llm = llm_interface
        self.registry = ToolRegistry()
        self.gate = BlastGate()
        self.max_loops = 5 
        self.tool_schemas = json.dumps(self.registry.get_all_schemas(), indent=2)
        
        # FIX 3: The State Cache. Holds the active memory context during security pauses.
        self.active_sessions = {}
        
        # FIX 2: Memory constraint threshold (characters)
        self.max_memory_chars = 6000

    def _build_system_prompt(self) -> str:
        # We clarify the prompt to prevent literal copying and force string outputs
        return f"""You are V, an autonomous AI agent.
AVAILABLE TOOLS:
{self.tool_schemas}

You MUST respond with a single valid JSON object. Do not include markdown formatting.
Format:
{{
  "Thought": "Your step-by-step reasoning",
  "Action": "Exact tool name, or 'None' if finished",
  "Action_Input": {{ "exact_parameter_name": "value" }}, 
  "Final_Answer": "Your response to the user AS A PLAIN STRING (only populate if Action is 'None')"
}}
"""

    def _compress_memory(self, memory_context: str) -> str:
        """
        FIX 2: The Sliding Window. Prevents the context avalanche by slicing out the middle 
        of the memory string if it gets too large, preserving the system prompt and recent observations.
        """
        if len(memory_context) > self.max_memory_chars:
            head_cut = 2000
            tail_cut = 3500
            return memory_context[:head_cut] + "\n...[SYSTEM LOG: OLD MEMORY COMPRESSED]...\n" + memory_context[-tail_cut:]
        return memory_context

    def execute_react_loop(self, user_query: Optional[str] = None, session_id: Optional[str] = None, user_auth: Optional[str] = None) -> str:
        """
        The main execution loop. Can be initialized fresh or resumed from a HITL pause.
        """
        # FIX 3: State Resumption
        if session_id and session_id in self.active_sessions and user_auth:
            session = self.active_sessions[session_id]
            if user_auth.strip().upper() in ["Y", "YES", "GO AHEAD"]:
                # User approved. Execute the paused physical action.
                observation = self.registry.execute_tool(session["tool_name"], **session["action_args"])
                memory_context = session["memory_context"] + f"\nObservation: {observation}\n"
                iteration_start = session["iteration"] + 1
            else:
                # User denied.
                memory_context = session["memory_context"] + "\nObservation: SYSTEM_ERROR: User explicitly denied execution.\n"
                iteration_start = session["iteration"] + 1
            
            # Flush the cache
            del self.active_sessions[session_id]
        else:
            # Fresh execution
            session_id = str(uuid.uuid4())
            memory_context = self._build_system_prompt() + f"\nUser Query: {user_query}\n"
            iteration_start = 0

        for iteration in range(iteration_start, self.max_loops):
            # Apply memory compression before feeding to the LLM
            memory_context = self._compress_memory(memory_context)
            
            # The Brain executes
            response_text = self.llm.generate(memory_context)
            memory_context += f"\nV: {response_text}\n"
            
            print(f"\n[DEBUG] V's Raw Output (Loop {iteration}):\n{response_text}")
            # FIX 1: Robust JSON Parsing
            try:
                # Strip potential markdown code blocks the LLM might hallucinate
                clean_text = re.sub(r'```json|```', '', response_text).strip()
                parsed = json.loads(clean_text)
            except json.JSONDecodeError:
                observation = "SYSTEM_ERROR: Output must be strictly valid JSON."
                memory_context += f"Observation: {observation}\n"

                print(f"[DEBUG] System Feed:\n{observation}")

                continue
                
            # Check for termination
            if parsed.get("Final_Answer"):
                final_ans = parsed["Final_Answer"]
                # Forcing the output to be a string so .startswith() never crashes
                return final_ans if isinstance(final_ans, str) else json.dumps(final_ans)
                
            tool_name = parsed.get("Action")
            action_args = parsed.get("Action_Input", {})
            
            # Execute tool logic
            if not tool_name or tool_name == "None":
                 observation = "SYSTEM_ERROR: No action specified but no Final_Answer provided."
            elif tool_name not in self.registry.tools:
                 observation = f"SYSTEM_ERROR: Tool '{tool_name}' not found."
            else:
                 tool_instance = self.registry.tools[tool_name]
                 gate_check = self.gate.evaluate_execution(tool_name, tool_instance.security_tier, action_args)
                 
                 if not gate_check["approved"]:
                     if gate_check.get("reason") == "HITL_REQUIRED":
                         # FIX 3: Cache the exact state before freezing
                         self.active_sessions[session_id] = {
                             "memory_context": memory_context,
                             "tool_name": tool_name,
                             "action_args": action_args,
                             "iteration": iteration
                         }
                         return f"SESSION:{session_id}|PAUSED_FOR_USER_AUTHORIZATION:\n{gate_check['ui_prompt']}"
                     else:
                         observation = f"SYSTEM_ERROR: Execution blocked. {gate_check['reason']}"
                 else:
                     observation = self.registry.execute_tool(tool_name, **action_args)
            
            print(f"[DEBUG] Tool Observation:\n{observation}")
            memory_context += f"Observation: {observation}\n"

        return "SYSTEM_ERROR: Max reasoning loops exceeded without reaching a final answer. Execution halted."