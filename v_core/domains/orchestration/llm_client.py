import json
import requests

class OllamaClient:
    """
    Connects to a local Ollama instance. 
    Enforces JSON output natively to prevent ReAct loop crashes.
    """
    def __init__(self, model_name: str = "llama3"):
        self.model_name = model_name
        self.api_url = "http://127.0.0.1:11434/api/generate"
        
    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            # We strictly enforce JSON mode at the API level
            "format": "json" 
        }
        
        try:
            response = requests.post(self.api_url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "{}")
        except requests.exceptions.ConnectionError:
            return '{"SYSTEM_ERROR": "Failed to connect to Ollama. Is the server running?"}'
        except Exception as e:
            return f'{{"SYSTEM_ERROR": "LLM generation failed: {str(e)}"}}'