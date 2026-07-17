from typing import Dict, Any, List, Optional

# Your existing imports stay exactly the same
from v_core.domains.tools.filesystem.directory_scanner import DirectoryScanner
from v_core.domains.tools.filesystem.file_reader import FileReader
from v_core.domains.tools.iots.universal_iot_bridge import BambuController
from v_core.domains.tools.system.command_executor import CommandExecutor
from v_core.domains.tools.web.web_scraper import WebScraper
from v_core.domains.tools.p_apis.rest_caller import RESTCaller
from v_core.domains.tools.preconditions import BaseTool

class ToolRegistry:
    """
    The central switchboard for V's capabilities.
    Loads tools into memory and routes execution requests from the Orchestrator.
    """
    def __init__(self):
        # Your existing tool mapping remains completely intact
        self.tools = {
            "directory_scanner": DirectoryScanner(),
            "file_reader": FileReader(),
            "universal_iot_bridge": BambuController(),
            "command_executor": CommandExecutor(),
            "web_scraper": WebScraper(),
            "rest_caller": RESTCaller()
        }

    # --- NEW METHODS FOR THE ORCHESTRATOR BRIDGE ---

    def has_tool(self, tool_name: str) -> bool:
        """Helper for the Orchestrator to verify tool existence before execution."""
        return tool_name in self.tools

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Safely retrieves the instantiated BaseTool object."""
        return self.tools.get(tool_name)

    # --- YOUR EXISTING SCHEMA METHODS ---

    def get_all_schemas(self) -> List[dict]:
        """
        Pulls the structured JSON schemas from all registered tools.
        Injected into V's system prompt so she knows her exact capabilities.
        """
        return [tool.get_schema() for tool in self.tools.values()]

    def get_all_tool_descriptions(self) -> str:
        """
        Returns a formatted string of all registered tools and their descriptions
        so the Orchestrator can inject them into the system prompt.
        """
        if not self.tools:
            return "No tools currently registered."
            
        descriptions = []
        for name, tool in self.tools.items():
            desc = getattr(tool, '__doc__', 'No description available.').strip()
            descriptions.append(f"- {name}: {desc}")
            
        return "\n".join(descriptions)

# Export a single singleton instance for the entire app to use
registry = ToolRegistry()