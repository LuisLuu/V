from typing import Dict, Any, List, Optional

from agents.tools.filesystem.directory_scanner import DirectoryScanner
from agents.tools.filesystem.file_reader import FileReader
from agents.tools.iots.universal_iot_bridge import BambuController
from agents.tools.system.command_executor import CommandExecutor
from agents.tools.system.task_tool import TaskManagerTool
from agents.tools.web.web_scraper import WebScraper
from agents.tools.p_apis.rest_caller import RESTCaller
from agents.tools.preconditions import BaseTool
from agents.tools.web.search_api import SearchAPI

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
            "rest_caller": RESTCaller(),
            "task_manager": TaskManagerTool()
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