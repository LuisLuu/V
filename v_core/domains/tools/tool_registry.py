from typing import Dict, Any, List, Optional

from v_core.domains.tools.filesystem.directory_scanner import DirectoryScanner
from v_core.domains.tools.filesystem.file_reader import FileReader
from v_core.domains.tools.iots.universal_iot_bridge import BambuController
from v_core.domains.tools.system.command_executor import CommandExecutor
from v_core.domains.tools.web.web_scraper import WebScraper
from v_core.domains.tools.p_apis.rest_caller import RESTCaller
from v_core.domains.tools.preconditions import BaseTool
from v_core.domains.tools.web.search_api import SearchAPI

class ToolRegistry:
    """
    The central switchboard for V's capabilities.
    """
    def __init__(self):
        self.tools = {
            "directory_scanner": DirectoryScanner(),
            "file_reader": FileReader(),
            "universal_iot_bridge": BambuController(),
            "command_executor": CommandExecutor(),
            "search_api": SearchAPI(),             
            "web_scraper": WebScraper(),
            "rest_caller": RESTCaller()
        }

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self.tools

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        return self.tools.get(tool_name)

    def get_all_schemas(self) -> List[dict]:
        return [tool.get_schema() for tool in self.tools.values()]

    def get_all_tool_descriptions(self) -> str:
        if not self.tools:
            return "No tools currently registered."
            
        descriptions = []
        for name, tool in self.tools.items():
            desc = getattr(tool, 'description', getattr(tool, '__doc__', '')).strip()
            descriptions.append(f"- {name}: {desc}")
            
        return "\n".join(descriptions)

# Export singleton instance
registry = ToolRegistry()