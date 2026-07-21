# v_backend/routers/chat_routes.py
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

# Import the actual function you built, not an imaginary class
from v_core.domains.orchestration.state_machine import run_cognitive_graph

api_router = APIRouter()

class ChatPayload(BaseModel):
    """Enforces strict structural typing for incoming web requests."""
    message: Optional[str] = None
    session_id: Optional[str] = None
    user_auth: Optional[str] = None

@api_router.post("/")
async def talk_to_v(payload: ChatPayload):
    """
    Ingests a user prompt, executes the async cognitive graph, 
    collects the streamed tokens, and returns the final synthesized string.
    """
    if not payload.message:
        raise HTTPException(status_code=400, detail="Payload must contain a 'message'.")

    try:
        # Create the queue required by your state machine
        yield_queue = asyncio.Queue()
        chat_history = [] # Placeholder until session memory is wired up
        
        # Fire off the cognitive graph as a background task
        graph_task = asyncio.create_task(
            run_cognitive_graph(payload.message, yield_queue, chat_history)
        )
        
        final_response = ""
        
        # Consume the queue to build the final string
        while True:
            item = await yield_queue.get()
            
            # The state machine signals it is finished
            if item["type"] == "done":
                break
                
            # Stitch the LLM tokens together
            elif item["type"] == "token":
                final_response += item["content"]
                
            # (Optional) You could log item["type"] == "status" or "warning" here 
            # to see the planner/tool execution steps in your server console.
            elif item["type"] in ["status", "warning"]:
                print(f"[{item['type'].upper()}]: {item['content']}")

        # Ensure the background task cleans up properly
        await graph_task
        
        return {"v_response": final_response}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SYSTEM_CRASH: {str(e)}")