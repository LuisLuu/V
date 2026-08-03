# agents/tools/system/bypass_tool.py

from typing import Any, Dict

from agents.tools.preconditions import BaseTool, SecurityTier


class ConversationalBypass(BaseTool):
    """A pseudo-tool that acts as a pressure valve for the LLM.

    Allows the agent to actively "choose" to just chat without firing real
    backend logic[cite: 10].
    """

    def __init__(self):
        self.name = "conversational_bypass"
        self.description = "Use this tool ONLY for casual chat, greetings, jokes, asking for clarification, or recapping the conversation[cite: 10]."
        self.security_tier = SecurityTier.READ
        self.preconditions = []

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    def execute(self, **kwargs) -> str:
        # This string will be injected into the tool_results array, silently
        # nudging the Synthesizer to rely on its RAM context window[cite: 10].
        return "System Note: No external action taken. Proceed to synthesize response using only the conversation history."