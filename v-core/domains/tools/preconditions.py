# v-core/domains/tools/preconditions.py
from enum import Enum
from typing import List, Callable, Any

class SecurityTier(Enum):
    READ = "autonomous"              # Safe to run (e.g., check time, read local file)
    WRITE = "logged_autonomous"      # Safe but leaves an audit trail (e.g., write to sandbox)
    DESTRUCTIVE = "human_approval"   # Hard-stops the pipeline (e.g., delete files, external API POST)

class BaseTool:
    """
    No tool executes without passing the harness gates.
    """
    name: str = "Unassigned"
    description: str = "Tool description for the LLM"
    security_tier: SecurityTier = SecurityTier.READ
    
    # Causal Preconditions: Fast computational sensors. 
    # What MUST be true before this tool is even considered?
    preconditions: List[Callable[[], bool]] = []

    def verify_preconditions(self) -> bool:
        """
        Runs before execution. If this returns False, the orchestrator
        intercepts the failure instead of letting the LLM hallucinate a fix.
        """
        if not self.preconditions:
            return True
        return all(condition() for condition in self.preconditions)

    def execute(self, **kwargs) -> Any:
        """
        The actual tool logic. Must be overridden by subclasses.
        """
        raise NotImplementedError("Every tool must implement its own execution logic.")