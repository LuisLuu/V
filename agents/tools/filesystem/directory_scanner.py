# v_core/domains/tools/filesystem/directory_scanner.py
import os
from typing import Dict, Any, List
from agents.tools.preconditions import BaseTool, SecurityTier

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

    def execute(self, directory_path: str = ".", max_depth: int = 2, max_items: int = 100, **kwargs) -> dict:
        import os # Local import to ensure availability during execution
        
        # Hardened LLM hallucination fallback (sometimes they pass positional args as kwargs)
        target_path = kwargs.get('path', directory_path)

        if not os.path.exists(target_path):
            return {"status": "error", "message": f"Directory not found: {target_path}"}

        item_count = 0

        def scan_recursive(current_path, current_depth) -> dict:
            nonlocal item_count
            
            # Consistent return type: always a dict with a notice, never a raw string
            if current_depth > max_depth:
                return {"_notice": "MAX_DEPTH_REACHED"}
            
            structure = {}
            try:
                # Using 'with' ensures the OS safely closes the directory iterator 
                # preventing memory/file descriptor leaks during massive scans
                with os.scandir(current_path) as it:
                    for entry in it:
                        if item_count >= max_items:
                            structure["_notice"] = f"TRUNCATED: Exceeded {max_items} items to protect context window."
                            return structure
                            
                        item_count += 1
                        
                        if entry.is_dir():
                            structure[entry.name] = {
                                "type": "DIR",
                                "contents": scan_recursive(entry.path, current_depth + 1)
                            }
                        elif entry.is_file():
                            structure[entry.name] = "FILE"
                            
            except PermissionError:
                 return {"_notice": "PERMISSION_DENIED"}
            except Exception as e:
                 return {"_notice": f"ERROR: {str(e)}"}
                 
            return structure

        # Initialize the recursion
        scanned_data = scan_recursive(target_path, 1)

        return {
            "status": "success",
            "path": target_path,
            "total_items_scanned": item_count,
            "contents": scanned_data
        }