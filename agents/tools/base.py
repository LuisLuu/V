# agents/tools/base.py
from pydantic import BaseModel, Field
from typing import Any

class BaseTool(BaseModel):
    """
    The master template for all tools in V's ecosystem.
    Enforces a strict security tier and execution standard.
    """
    name: str
    description: str
    security_tier: str = Field(default="SAFE", description="Can be SAFE, WRITE, or DESTRUCTIVE")

    def verify_preconditions(self) -> bool:
        """
        Sensors run here before the tool executes. 
        If this returns False, the tool is hard-blocked.
        """
        return True

    async def execute(self, **kwargs) -> Any:
        """
        The actual logic of the tool. Must be overridden by child classes.
        """
        raise NotImplementedError("Every tool must implement an execute method.")