import subprocess
import os
from v_core.domains.tools.preconditions import BaseTool, SecurityTier

class CommandExecutor(BaseTool):
    """
    Executes terminal commands on the local operating system.
    Protected by strict semantic Blast Gates and timeouts.
    """
    def __init__(self):
        self.name = "command_executor"
        self.description = "Executes shell commands on the local machine (e.g., dir, ls, ping, python scripts)."
        # High security operation. 
        self.security_tier = SecurityTier.WRITE
        self.preconditions = [self._check_os]
        
        # The Semantic Blast Gate: Hardcoded blocklist of destructive commands
        self.blocklist = [
            "rm -rf", "del /f", "format ", "diskpart", "mkfs", "dd ", 
            "shutdown", "reboot", "sudo ", "chmod ", "chown ", "reg delete"
        ]

    def _check_os(self) -> bool:
        """Sensor: Verifies we are running on a recognized OS."""
        return os.name in ['nt', 'posix']

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The command string to execute in the terminal."
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Max execution time in seconds. Defaults to 10 to prevent hanging."
                        }
                    },
                    "required": ["command"]
                }
            }
        }

    def execute(self, command: str, timeout: int = 10) -> str:
        """
        Runs the command through the semantic filter, then executes via subprocess.
        """
        # 1. The Blast Gate Check
        command_lower = command.lower()
        for blocked_term in self.blocklist:
            if blocked_term in command_lower:
                return f"SYSTEM_HALT: Command blocked by Blast Gate. '{blocked_term}' is strictly forbidden."
        
        try:
            # 2. Safe Execution Pipeline
            # We use shell=True so V can run standard commands like 'dir', but we 
            # mitigate the risk heavily with the blocklist and strict timeout limits.
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            # 3. Format the Output
            output = result.stdout.strip()
            error = result.stderr.strip()
            
            # Protect the context window from massive terminal dumps
            max_chars = 4000
            if len(output) > max_chars:
                output = f"...[SYSTEM WARNING: Output truncated. Showing final {max_chars} chars]...\n" + output[-max_chars:]
            
            if result.returncode == 0:
                return output if output else "Command executed successfully (no output)."
            else:
                return f"EXECUTION_FAILED (Code {result.returncode}):\n{error}"
                
        except subprocess.TimeoutExpired:
            # Prevents indefinite hangs and CPU exhaustion
            return f"SYSTEM_ERROR: Command timed out after {timeout} seconds."
        except Exception as e:
            return f"SYSTEM_ERROR: Unexpected error executing command: {str(e)}"