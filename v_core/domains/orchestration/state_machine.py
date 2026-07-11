# v-core/domains/orchestration/state_machine.py
from enum import Enum
from v_core.domains.tools.preconditions import SecurityTier

class Orchestrator:
    """
    The main execution loop. It manages memory sensors, triggers compaction, 
    evaluates tool preconditions, and enforces blast gates.
    """
    def __init__(self, ram_window, compaction_engine, tool_registry):
        self.ram = ram_window
        self.compaction = compaction_engine
        self.tools = tool_registry

    def run_task(self, user_input: str) -> str:
        # Put the new task on the active workbench
        self.ram.append_node("user", user_input, status="active")
        
        max_iterations = 5
        current_loop = 0
        
        while current_loop < max_iterations:
            # 1. The Memory Sensor Check
            if self.ram.is_critical():
                # The desk is cluttered. Pause and sweep.
                condensed_state = self.compaction.compact_context(self.ram.active_messages)
                self.ram.clear_compacted_nodes(condensed_state)
            
            # 2. Reason (The LLM Call)
            # In a real implementation, this streams to your local Qwen 2.5
            action_plan = self._call_qwen_llm(self.ram.get_working_context())
            
            # 3. Route the Action
            if not action_plan.get("tool_call"):
                # No tools needed. Task is done or it's a regular chat response.
                self.ram.append_node("assistant", action_plan["text"], status="active")
                return action_plan["text"]
                
            tool_name = action_plan["tool_call"]["name"]
            tool_args = action_plan["tool_call"]["args"]
            tool_instance = self.tools.get_tool(tool_name)
            
            # 4. The Blast Gate (Human-in-the-Loop)
            if tool_instance.security_tier == SecurityTier.DESTRUCTIVE:
                # HARD STOP. Pause the loop and alert the FastAPI transport layer.
                return f"SYSTEM_HALT: Tool '{tool_name}' requires human approval."
                
            # 5. Computational Sensors (The Feedback Loop)
            if not tool_instance.verify_preconditions():
                # Catch the error and shove it back into RAM so V can self-correct
                error_msg = f"Observation: Preconditions failed for {tool_name}. Check paths/auth."
                self.ram.append_node("system", error_msg, status="ephemeral")
                current_loop += 1
                continue 
                
            # 6. Act & Observe
            try:
                result = tool_instance.execute(**tool_args)
                # Success! Tag as completed so the Compaction Engine can file it to ROM later
                self.ram.append_node("system", f"Tool Result: {result}", status="completed")
            except Exception as e:
                # Catch actual execution crashes
                self.ram.append_node("system", f"Tool Error: {str(e)}", status="ephemeral")
                
            current_loop += 1
            
        return "Task failed: Exceeded maximum reasoning loops. Compounding error prevented."