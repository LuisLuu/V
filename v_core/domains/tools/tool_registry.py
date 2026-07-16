from typing import Dict, Any, List

from v_core.domains.tools.filesystem.directory_scanner import DirectoryScanner
from v_core.domains.tools.filesystem.file_reader import FileReader
from v_core.domains.tools.iots.bambu_controller import BambuController
from v_core.domains.tools.system.command_executor import CommandExecutor
from v_core.domains.tools.web.web_scraper import WebScraper
from v_core.domains.tools.p_apis.rest_caller import RESTCaller

class ToolRegistry:
    """
    The central switchboard for V's capabilities.
    Loads tools into memory and routes execution requests from the Orchestrator.
    """
    def __init__(self):
        self.tools = {
            "directory_scanner": DirectoryScanner(),
            "file_reader": FileReader(),
            "bambu_controller": BambuController(),
            "command_executor": CommandExecutor(),
            "web_scraper": WebScraper(),
            "rest_caller": RESTCaller()
        }

    def get_all_schemas(self) -> List[dict]:
        """
        Pulls the structured JSON schemas from all registered tools.
        Injected into V's system prompt so she knows her exact capabilities.
        """
        return [tool.get_schema() for tool in self.tools.values()]

    def execute_tool(self, tool_name: str, tool_params: dict | None = None) -> str:
        """Executes the mapped tool with the provided input parameters."""
        if tool_params is None:
            tool_params = {}
            
        if tool_name not in self.tools:
            return f"Error: Tool '{tool_name}' not found."
            
        # Unpack the parameters into the tool's run method
        return self.tools[tool_name].run(**tool_params)
    
    def get_all_tool_descriptions(self) -> str:
        """
        Returns a formatted string of all registered tools and their descriptions
        so the Orchestrator can inject them into the system prompt.
        """
        if not self.tools:
            return "No tools currently registered."
            
        descriptions = []
        for name, tool in self.tools.items():
            # Assuming your tool objects have a __doc__ or description attribute
            desc = getattr(tool, '__doc__', 'No description available.').strip()
            descriptions.append(f"- {name}: {desc}")
            
        return "\n".join(descriptions)