# v_core/domains/tools/filesystem/directory_scanner.py
import os
from typing import Dict, Any, List
from v_core.domains.tools.preconditions import BaseTool, SecurityTier

class DirectoryScanner(BaseTool):
    """
    Allows the agent to scan a local directory and return a structural map
    of its contents, including files and subdirectories.
    """
    def __init__(self):
        self.name = "directory_scanner"
        self.description = "Scans a specific local file directory and returns a structured list of its contents."
        # Scanning is a safe read operation, so it runs autonomously without prompting the user.
        self.security_tier = SecurityTier.READ  
        self.preconditions = [self._check_os_access]

    def _check_os_access(self) -> bool:
        """
        Computational Sensor: Verifies the standard OS library is available
        before attempting to execute the tool.
        """
        try:
            import os
            return True
        except ImportError:
            return False

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory_path": {
                            "type": "string",
                            "description": "The absolute or relative path to the directory to scan."
                        },
                        "max_depth": {
                            "type": "integer",
                            "description": "How many subfolders deep to scan. Defaults to 1 to prevent massive dumps."
                        }
                    },
                    "required": ["directory_path"]
                }
            }
        }

    def execute(self, directory_path: str = ".", max_depth: int = 1) -> Dict[str, Any]:
        """
        The physical action of scanning the drive. 
        Returns structured JSON rather than a messy string.
        """
        if not os.path.exists(directory_path):
            return {"status": "error", "message": f"Directory not found: {directory_path}"}
        
        if not os.path.isdir(directory_path):
            return {"status": "error", "message": f"Path is a file, not a directory: {directory_path}"}

        structure = {}
        
        try:
            # We use os.scandir for high-performance, low-latency directory traversal
            for entry in os.scandir(directory_path):
                if entry.is_dir():
                    structure[entry.name] = "DIR"
                elif entry.is_file():
                    structure[entry.name] = "FILE"
                    
            return {
                "status": "success",
                "path": directory_path,
                "contents": structure
            }
            
        except PermissionError:
            return {"status": "error", "message": f"Permission denied accessing: {directory_path}"}
        except Exception as e:
             return {"status": "error", "message": f"Unexpected error: {str(e)}"}