import json
import requests

class OllamaClient:
    def __init__(self, model_name: str = "llama3", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url

    # Notice the 'str | None' fix here
    def generate(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.7) -> str:
        url = f"{self.base_url}/api/generate"
        

        payload = {
            "model": self.model_name,
            "prompt": prompt, 
            "system": system_prompt,  
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            raise RuntimeError(f"Cognitive core offline: {str(e)}")

        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            raise RuntimeError(f"Cognitive core offline: {str(e)}")