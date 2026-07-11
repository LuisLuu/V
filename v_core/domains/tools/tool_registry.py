from typing import Dict, Type, Any
from .preconditions import BaseTool

class ToolRegistry:
    def __init__(self):
        # A dictionary mapping tool names to their actual class instances
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """Adds a tool to the internal bins."""
        self._tools[tool.name] = tool

    def get_lightweight_index(self) -> str:
        """
        PROGRESSIVE DISCLOSURE: Phase 1
        This is the ONLY thing V sees in her default system prompt.
        It costs barely any tokens.
        """
        if not self._tools:
            return "No tools available."
        
        index = "Available Tools (Call by name to get full schema):\n"
        for name, tool in self._tools.items():
            index += f"- {name}: {tool.description}\n"
        return index

    def get_tool_schema(self, tool_name: str) -> dict:
        """
        PROGRESSIVE DISCLOSURE: Phase 2
        V only receives this massive JSON schema WHEN she decides to use the tool.
        """
        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool {tool_name} does not exist.")
        
        # In a real implementation, this would return the Pydantic schema 
        # or detailed JSON required to format the arguments correctly.
        return tool.get_schema()