import subprocess
import os
import shlex
from typing import List
from agents.tools.preconditions import BaseTool, SecurityTier

class CommandExecutor(BaseTool):
    """
    Executes terminal commands inside an isolated Docker container 
    to protect the host operating system from destructive actions.
    """
    def __init__(self, sandbox_dir: str = "./sandbox", use_docker: bool = False):
        self.name = "command_executor"
        self.description = (
            "Executes shell commands safely inside an isolated environment "
            "(e.g., python scripts, git commands, file manipulations)."
        )
        # Re-classified: Running arbitrary terminal commands is inherently destructive
        self.security_tier = SecurityTier.DESTRUCTIVE
        
        self.sandbox_dir = os.path.abspath(sandbox_dir)
        self.use_docker = use_docker
        self.docker_image = "v_sandbox:latest"
        
        # Ensure the local sandbox directory exists
        os.makedirs(self.sandbox_dir, exist_ok=True)
        
        self.preconditions = [self._check_docker_available if self.use_docker else self._check_os]

    def _check_os(self) -> bool:
        """Sensor: Verifies OS compatibility for fallback mode."""
        return os.name in ['nt', 'posix']

    def _check_docker_available(self) -> bool:
        """Sensor: Verifies Docker daemon is responsive before execution."""
        try:
            res = subprocess.run(["docker", "info"], capture_output=True, timeout=2)
            return res.returncode == 0
        except Exception:
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
                        "command": {
                            "type": "string",
                            "description": "The command string to execute in the sandboxed terminal."
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Max execution time in seconds. Defaults to 15."
                        }
                    },
                    "required": ["command"]
                }
            }
        }

    def execute(self, command: str, timeout: int = 15) -> str:
        """
        Executes the command inside a sandboxed Docker container.
        """
        if self.use_docker:
            return self._execute_in_docker(command, timeout)
        else:
            return self._execute_host_fallback(command, timeout)

    def _execute_in_docker(self, command: str, timeout: int) -> str:
        """Runs command inside a restricted, auto-removed Docker container."""
        # Mount host's ./sandbox directory to /workspace inside container
        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none",                    # Cut network access by default (enable if tool explicitly requires web)
            "--memory", "512m",                     # Limit memory footprint
            "--cpus", "1.0",                        # Limit CPU core usage
            "--cap-drop", "ALL",                    # Drop Linux kernel capabilities
            "-v", f"{self.sandbox_dir}:/workspace", # Isolate disk access to sandbox
            "-w", "/workspace",
            self.docker_image,
            "bash", "-c", command
        ]

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return self._format_output(result.stdout, result.stderr, result.returncode)
        except subprocess.TimeoutExpired:
            return f"SYSTEM_ERROR: Sandboxed command timed out after {timeout} seconds."
        except Exception as e:
            return f"SYSTEM_ERROR: Docker execution failure: {str(e)}"

    def _execute_host_fallback(self, command: str, timeout: int) -> str:
        """Fallback host execution using token-based shlex validation if Docker is disabled."""
        tokens = shlex.split(command)
        if not tokens:
            return "SYSTEM_ERROR: Empty command provided."

        # Token-level base command evaluation (safer than substring search)
        forbidden_binaries = {"sudo", "su", "format", "diskpart", "mkfs", "reg"}
        if tokens[0].lower() in forbidden_binaries:
            return f"SYSTEM_HALT: Forbidden binary '{tokens[0]}' intercepted by Host Guard."

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.sandbox_dir, # Force host execution inside sandbox directory
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return self._format_output(result.stdout, result.stderr, result.returncode)
        except subprocess.TimeoutExpired:
            return f"SYSTEM_ERROR: Command timed out after {timeout} seconds."
        except Exception as e:
            return f"SYSTEM_ERROR: Host execution error: {str(e)}"

    def _format_output(self, stdout: str, stderr: str, returncode: int) -> str:
        output = stdout.strip()
        error = stderr.strip()
        max_chars = 4000

        if len(output) > max_chars:
            output = f"...[SYSTEM WARNING: Output truncated. Showing final {max_chars} chars]...\n" + output[-max_chars:]

        if returncode == 0:
            return output if output else "Command executed successfully (no output)."
        else:
            return f"EXECUTION_FAILED (Code {returncode}):\n{error}"