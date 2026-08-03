# v_core/domains/tools/filesystem/file_reader.py

import os

from agents.tools.preconditions import BaseTool, SecurityTier


class FileReader(BaseTool):
    """Reads the contents of a local file and returns it as a string.

    Includes a safety truncate and metadata wrapper to prevent blowing out the
    LLM context window[cite: 8].
    """

    def __init__(self):
        self.name = "file_reader"
        self.description = "Reads the raw text content of a specific file. Returns the file's text[cite: 8]."
        # Safe operation. No human approval needed to read a file[cite: 8].
        self.security_tier = SecurityTier.READ
        self.preconditions = [self._check_file_io]
        # 15,000 chars is roughly 3,000 tokens. Safe buffer for Qwen 2.5 context[cite: 8].
        self.max_chars = 15000

    def _check_file_io(self) -> bool:
        """Sensor: Ensure standard OS I/O is available[cite: 8]."""
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
                        "file_path": {
                            "type": "string",
                            "description": "The absolute path to the file you want to read[cite: 8].",
                        }
                    },
                    "required": ["file_path"],
                },
            },
        }

    def execute(self, file_path: str) -> str:
        """The physical action of cracking the file open and appending metadata context[cite: 8]."""
        if not os.path.exists(file_path):
            return f"SYSTEM_ERROR: File not found at {file_path}"

        if not os.path.isfile(file_path):
            return f"SYSTEM_ERROR: Path is a directory, not a file: {file_path}. Use directory_scanner instead[cite: 8]."

        try:
            # Enforce UTF-8 reading to prevent weird encoding crashes[cite: 8]
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # The Context Window Protector with Metadata Wrap[cite: 8]
            status = "Read Fully"
            if len(content) > self.max_chars:
                content = content[: self.max_chars]
                status = f"TRUNCATED for safety (Max {self.max_chars} chars)[cite: 8]"

            return f"""
--- FILE METADATA ---
Path: {file_path}
Size: {os.path.getsize(file_path)} bytes
Status: {status}
---------------------
{content}
"""

        except UnicodeDecodeError:
            # Catches attempts to read images, compiled firmware, or proprietary binaries[cite: 8]
            return f"SYSTEM_ERROR: File at {file_path} is binary or uses an unsupported encoding. Cannot read as text[cite: 8]."
        except PermissionError:
            return f"SYSTEM_ERROR: Permission denied. Cannot read {file_path}. Check OS locks[cite: 8]."
        except Exception as e:
            return f"SYSTEM_ERROR: Unexpected error reading file: {str(e)}"