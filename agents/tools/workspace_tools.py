# v_core/domains/tools/workspace_tools.py
import subprocess
from pathlib import Path
from pydantic import BaseModel, Field
from agents.tools.base import BaseTool # Assuming your base tool structure
from agents.harness.sensors import workspace_is_intact

class WorkspaceWriter(BaseTool):
    name: str = "workspace_writer"
    description: str = "Writes a code script or text file strictly to the isolated ./v_workspace directory."
    security_tier: str = "WRITE" # Auto-approved by the Blast Gate

    def verify_preconditions(self) -> bool:
        return workspace_is_intact()

    async def execute(self, filename: str, content: str) -> str:
        workspace = Path("./v_workspace").resolve()
        file_path = (workspace / filename).resolve()
        
        # Redundant Path Traversal Defense: Hard-block escapes like "../../"
        if workspace not in file_path.parents and file_path != workspace / filename:
            return f"Error: Path traversal attempt blocked. Must write inside {workspace}"
            
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Success: File '{filename}' written and ready for execution or review."
        except Exception as e:
            return f"Failed to write file: {e}"

class WorkspaceExecutor(BaseTool):
    name: str = "workspace_executor"
    description: str = "Executes a specific script or terminal command inside the workspace."
    security_tier: str = "DESTRUCTIVE" # Triggers the Blast Gate HITL
    
    def verify_preconditions(self) -> bool:
        return workspace_is_intact()

    async def execute(self, command: str) -> str:
        workspace = Path("./v_workspace").resolve()
        try:
            # Executes the command strictly with the workspace as the Current Working Directory (CWD)
            result = subprocess.run(
                command, 
                shell=True, 
                cwd=workspace, 
                capture_output=True, 
                text=True, 
                timeout=30 # Circuit Breaker: Kills infinite loops
            )
            
            output = result.stdout if result.returncode == 0 else result.stderr
            
            # Truncate output to prevent LLM context window overflow
            max_chars = 2000 
            if len(output) > max_chars:
                output = output[:max_chars] + f"\n...[Output truncated. Original length: {len(output)} chars]"
                
            return f"Execution Code: {result.returncode}\nOutput:\n{output}"
            
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out after 30 seconds. Script was terminated."
        except Exception as e:
            return f"System Error: {str(e)}"