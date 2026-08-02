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
        # For autonomous modes, you might set this to True, but never DESTRUCTIVE.
        self.auto_approve_writes = False 
        
    def evaluate_execution(self, tool_name: str, tier: SecurityTier, kwargs: dict) -> dict:
        """
        Evaluates if the LLM's requested action is safe to execute autonomously.
        Returns a strict dictionary schema for the FastAPI router to intercept.
        """
        logging.info(f"[BLAST GATE] Evaluating {tool_name} at tier {tier.name}...")

        # 1. Auto-Pass for Safe (READ) Operations
        if tier == SecurityTier.READ and self.auto_approve_reads:
            return {
                "approved": True,
                "status": "AUTO_APPROVED",
                "reason": f"System auto-approved {tier.name} operation."
            }
        
        # 2. Managed State for WRITE Operations
        if tier == SecurityTier.WRITE:
            if tool_name == "rest_caller" and str(kwargs.get("method", "")).upper() == "GET":
                return {
                    "approved": True,
                    "status": "AUTO_APPROVED",
                    "reason": "Safe GET request bypassed WRITE tier."
                }
                
            if self.auto_approve_writes:
                return {
                    "approved": True,
                    "status": "AUTO_APPROVED",
                    "reason": f"System auto-approved {tier.name} operation."
                }
            else:
                return self._trigger_hitl(tool_name, tier, kwargs)

        # 3. The Hard Stop for DESTRUCTIVE Operations
        if tier == SecurityTier.DESTRUCTIVE:
            # DESTRUCTIVE operations NEVER auto-approve, regardless of settings.
            return self._trigger_hitl(tool_name, tier, kwargs)
            
        return {
            "approved": False,
            "status": "BLOCKED",
            "reason": "UNKNOWN_TIER: Security tier not recognized. Execution blocked."
        }

    def _trigger_hitl(self, tool_name: str, tier: SecurityTier, kwargs: dict) -> dict:
        """
        Formats a structured Human-In-The-Loop (HITL) authorization request.
        The FastAPI router will use this to pause the LLM and ping the UI.
        """
        warning_msg = (
            f"⚠️ AUTHORIZATION REQUIRED: V is attempting a {tier.name} operation.\n"
            f"Tool: {tool_name}\n"
            f"Parameters: {kwargs}"
        )
        return {
            "approved": False, 
            "status": "HITL_REQUIRED", # Router intercepts this exact status string
            "ui_prompt": warning_msg,
            "tool_payload": {
                "name": tool_name,
                "kwargs": kwargs
            }
        }