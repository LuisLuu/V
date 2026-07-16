# v_core/domains/orchestration/sub_agents.py
import json
import logging
from v_core.domains.orchestration.llm_client import OllamaClient
from v_core.domains.memory.ram_window import RAMWindow

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
        
class ConversationalNode:
    """
    The chat fallback layer. Handles casual conversation and clarifies ambiguous intent.
    Utilizes a short-term RAM window to maintain conversational state.
    """
    def __init__(self, llm_interface: OllamaClient, ram: RAMWindow):
        self.llm = llm_interface
        self.ram = ram
        
        # FIXED: V's actual persona
        self.persona = """You are V, an autonomous AI entity equipped with various functions for file processing, local control, and web interaction. You are concise, logical, and highly efficient. You do not experience human emotions, but you are helpful, direct, and ready to assist the user."""

    def chat(self, user_query: str) -> str:
        logging.info("[CONVERSATIONAL NODE] Processing casual intent...")
        
        context_history = self.ram.get_recent_history(limit=5)
        system_prompt = f"{self.persona}\n\nRecent Conversation History:\n{context_history}\n\nRespond naturally to the user's latest input. If their request was ambiguous, ask for clarification."
        
        try:
            response = self.llm.generate(
                prompt=user_query,
                system_prompt=system_prompt,
                temperature=0.7
            )
            
            self.ram.add_interaction(role="user", content=user_query)
            self.ram.add_interaction(role="v", content=response)
            
            logging.info("[CONVERSATIONAL NODE] Response generated successfully.")
            return response
            
        except Exception as e:
            logging.error(f"[CONVERSATIONAL NODE] Chat generation failed. Error: {e}")
            return "I seem to be experiencing a cognitive glitch. Could you repeat that?"