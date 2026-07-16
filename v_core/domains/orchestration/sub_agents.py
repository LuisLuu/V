# v_core/domains/orchestration/sub_agents.py
import json
import logging
from v_core.domains.orchestration.llm_client import OllamaClient

class RouterNode:
    """
    The central triage layer. Analyzes user intent and routes the query 
    into one of four highly specialized execution paths.
    """
    def __init__(self, llm_interface: OllamaClient):
        self.llm = llm_interface

    def classify_intent(self, user_query: str) -> str:
        logging.info("[ROUTER NODE] Classifying user intent into the 4-tier matrix...")
        
        system_prompt = """You are the high-speed routing intelligence for an advanced AI ecosystem.
Your ONLY job is to analyze the user's input and classify their intent into exactly ONE of these four routes:

1. "CHAT": Conversational greetings, small talk, checking in, or asking for clarification. Requires zero tools.
2. "RESEARCH": Searching the web, gathering external facts, or reading online documentation.
3. "HARDWARE_IOT": Checking telemetry, verifying status, or controlling physical devices (e.g., 3D printers, microcontrollers).
4. "SYS_EXECUTE": Modifying local files, scanning directories, or executing operating system terminal commands.

You must output a strict JSON object with a single key 'Route'. The value must be the exact string of the chosen route. 
Do not include markdown, explanations, or conversational text.
Format example: {"Route": "HARDWARE_IOT"}
"""
        
        try:
            # Temperature locked to 0.1 to strip creativity and force a deterministic JSON route
            raw_response = self.llm.generate(
                prompt=user_query,
                system_prompt=system_prompt,
                temperature=0.1 
            )
            
            clean_json = raw_response.strip().strip('`').replace('json\n', '')
            parsed = json.loads(clean_json)
            
            route = parsed.get("Route", "CHAT").upper()
            
            # The safety catch: if it hallucinates a path, we fall back to harmless conversation
            valid_routes = ["CHAT", "RESEARCH", "HARDWARE_IOT", "SYS_EXECUTE"]
            if route not in valid_routes:
                route = "CHAT" 
                
            logging.info(f"[ROUTER NODE] Traffic successfully routed to: {route}")
            return route
            
        except Exception as e:
            logging.error(f"[ROUTER NODE] Classification failed, defaulting to CHAT fallback. Error: {e}")
            return "CHAT"