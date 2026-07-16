# v_backend/routers/event_streams.py
import json
import asyncio
from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse
from v_backend.routers.chat_routes import v_agent

router = APIRouter(prefix="/stream", tags=["Streaming"])

@router.get("/")
async def stream_v_cognition(message: str = Query(..., description="The user prompt to process")):
    """
    Exposes a Server-Sent Events (SSE) channel.
    Streams V's thoughts, tool actions, and raw observations down to the client in real-time.
    """
    async def event_generator():
        try:
            # Step 1: Tell the client we've initiated processing
            yield {
                "event": "status",
                "data": json.dumps({"message": "Initializing V's cognitive core..."})
            }
            await asyncio.sleep(0.1)

            # NOTE: In a full implementation, you would convert the Orchestrator's internal 
            # loop into a generator. For this testing phase, we simulate the stream steps 
            # pulling directly from the live network context.
            
            # Simulate streaming out the Thought phase
            yield {
                "event": "thought",
                "data": json.dumps({"thought": "Analyzing user request to scan directories or call tools."})
            }
            await asyncio.sleep(1)

            # Run the actual heavy lifting loop
            # If the Blast Gate triggers an intercept, it returns the session structure.
            response = v_agent.process_prompt(user_query=message)
            
            if response.startswith("SESSION:"):
                parts = response.split("|", 1)
                session_id = parts[0].split(":")[1]
                ui_prompt = parts[1]
                
                yield {
                    "event": "security_intercept",
                    "data": json.dumps({"session_id": session_id, "prompt": ui_prompt})
                }
            else:
                yield {
                    "event": "final_answer",
                    "data": json.dumps({"answer": response})
                }

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": f"STREAM_CRASH: {str(e)}"})
            }

    return EventSourceResponse(event_generator())