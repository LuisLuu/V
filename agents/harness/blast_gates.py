# v_core/domains/harness/blast_gates.py
import logging
from agents.tools.preconditions import SecurityTier

class BlastGate:
    """
    The central security interceptor. 
    Every tool call from the Orchestrator must pass through this gate before execution.
    """
    def __init__(self):
        # By default, we let V read data without bothering you.
        self.auto_approve_reads = True
        
    def evaluate_execution(self, tool_name: str, tier: str, kwargs: dict) -> dict:
        """
        Evaluates if the LLM's requested action is safe to execute autonomously,
        or if it requires physical human authorization.
        """
        logging.info(f"[BLAST GATE] Evaluating {tool_name} at tier {tier}...")

        # 1. Auto-Pass for Safe Operations
        if tier == SecurityTier.READ and self.auto_approve_reads:
            return {
                "approved": True, 
                "reason": f"Auto-approved {SecurityTier.READ} operation."
            }
        
        # 2. The Hard Stop for Write Operations
        if tier == SecurityTier.WRITE:
            warning_msg = (
                f"\n⚠️ ACTION REQUIRED: V is attempting to execute a {SecurityTier.WRITE} operation.\n"
                f"Tool: {tool_name}\n"
                f"Parameters: {kwargs}\n"
                f"Do you authorize this execution? (Y/N)"
            )
            return {
                "approved": False, 
                "reason": "HITL_REQUIRED",
                "ui_prompt": warning_msg
            }
            
        return {
            "approved": False,
            "reason": "UNKNOWN_TIER: Security tier not recognized. Execution blocked by default."
        }