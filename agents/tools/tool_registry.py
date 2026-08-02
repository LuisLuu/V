from typing import Dict, Any, List, Optional
from agents.tools.filesystem.directory_scanner import DirectoryScanner
from agents.tools.filesystem.file_reader import FileReader
from agents.tools.system.command_executor import CommandExecutor
from agents.tools.web.web_scraper import WebScraper
from agents.tools.p_apis.rest_caller import RESTCaller
from agents.tools.web.search_api import SearchAPI
from agents.tools.system.task_tool import TaskManagerTool
from agents.tools.preconditions import BaseTool
from agents.tools.system.bypass_tool import ConversationalBypass
from agents.tools.system.memory_tool import MemoryDraftTool
from agents.tools.workspace_tools import WorkspaceWriter, WorkspaceExecutor

class ToolRegistry:
    def __init__(self):
        self.tools = {
            "directory_scanner": DirectoryScanner(),
            "file_reader": FileReader(),
            "command_executor": CommandExecutor(),
            "search_api": SearchAPI(),             
            "web_scraper": WebScraper(),
            "rest_caller": RESTCaller(),
            "task_manager": TaskManagerTool(),
            "conversational_bypass": ConversationalBypass(),
            "draft_memory_update": MemoryDraftTool(),
            "workspace_writer": WorkspaceWriter(),
            "workspace_executor": WorkspaceExecutor(),
        }

    def register_tool(self, tool_name: str, tool_instance: Any):
        """Dynamically registers a new tool or sub-agent."""
        self.tools[tool_name] = tool_instance

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