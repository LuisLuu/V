# v_backend/routers/chat_routes.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from v_core.domains.orchestration.state_machine import Orchestrator
from v_core.domains.orchestration.llm_client import OllamaClient

router = APIRouter(prefix="/chat", tags=["Communication"])

# We initialize the agent globally here so her session memory 
# persists across multiple HTTP requests.
live_brain = OllamaClient(model_name="llama3")
v_agent = Orchestrator(llm_interface=live_brain)

class ChatPayload(BaseModel):
    """Enforces strict structural typing for incoming web requests."""
    message: Optional[str] = None
    session_id: Optional[str] = None
    user_auth: Optional[str] = None

@router.post("/")
def talk_to_v(payload: ChatPayload):
    """
    Ingests a user prompt, runs the ReAct loop, and returns the response.
    Can also resume a paused cognitive state if provided a session ID and auth flag.
    """
    try:
        if payload.session_id and payload.user_auth:
            # RESUME STATE: The user is authorizing a blocked action
            response = v_agent.execute_react_loop(
                session_id=payload.session_id, 
                user_auth=payload.user_auth
            )
        elif payload.message:
            # FRESH STATE: The user is asking a new question
            response = v_agent.execute_react_loop(user_query=payload.message)
        else:
            raise HTTPException(status_code=400, detail="Payload must contain either a 'message' or a 'session_id' with 'user_auth'.")
        
        return {"v_response": response}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SYSTEM_CRASH: {str(e)}")