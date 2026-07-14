# v_core/domains/tools/p_apis/rest_caller.py
import json
from v_core.domains.tools.preconditions import BaseTool, SecurityTier

class RESTCaller(BaseTool):
    """
    A universal adapter to interact with external REST APIs.
    Handles GET, POST, PUT, DELETE with custom headers and JSON payloads.
    """
    def __init__(self):
        self.name = "rest_caller"
        self.description = "Makes HTTP requests to REST APIs. Use this to pull schedules, send emails, or interact with web services."
        # Because this tool can POST/DELETE data externally, it must be carefully monitored.
        self.security_tier = SecurityTier.WRITE 
        self.preconditions = [self._check_requests]
        # Protects against massive JSON dumps from poorly optimized endpoints
        self.max_chars = 10000

    def _check_requests(self) -> bool:
        """Sensor: Verifies HTTP library is available."""
        try:
            import requests
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
                        "method": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "DELETE"],
                            "description": "The standard HTTP method to use."
                        },
                        "url": {
                            "type": "string",
                            "description": "The exact API endpoint URL."
                        },
                        "headers": {
                            "type": "string",
                            "description": "A JSON-formatted string of HTTP headers (e.g., for Authorization Bearer tokens)."
                        },
                        "payload": {
                            "type": "string",
                            "description": "A JSON-formatted string representing the request body (for POST/PUT)."
                        }
                    },
                    "required": ["method", "url"]
                }
            }
        }

    def execute(self, method: str, url: str, headers: str = "{}", payload: str = "{}") -> str:
        """
        The Universal Execution Pipeline.
        """
        import requests
        
        # 1. Parse the strings back into dictionaries
        try:
            parsed_headers = json.loads(headers)
            parsed_payload = json.loads(payload)
        except json.JSONDecodeError as e:
            return f"SYSTEM_ERROR: Invalid JSON provided for headers or payload. {str(e)}"

        try:
            # 2. Fire the Request
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=parsed_headers,
                json=parsed_payload if method.upper() in ["POST", "PUT", "PATCH"] else None,
                timeout=15
            )
            
            # 3. Handle specific HTTP error codes cleanly
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                # We return the first 500 chars of the error text because APIs often 
                # explain *why* it failed in the body (e.g., "Invalid Token").
                return f"API_ERROR: {str(e)} - Server Response: {response.text[:500]}"

            # 4. Extract and Truncate
            try:
                # Try to format as clean JSON if possible
                data = response.json()
                output = json.dumps(data, indent=2)
            except ValueError:
                output = response.text

            if len(output) > self.max_chars:
                # For JSON, we use a Head Cut (keeping the top). If we cut the bottom off, 
                # V can at least see the top-level keys and structure to reformulate her query.
                output = output[:self.max_chars] + f"\n...[SYSTEM WARNING: Payload truncated at {self.max_chars} chars.]"
            
            return output

        except requests.exceptions.Timeout:
            return "SYSTEM_ERROR: API request timed out after 15 seconds."
        except Exception as e:
            return f"SYSTEM_ERROR: Failed to call API: {str(e)}"