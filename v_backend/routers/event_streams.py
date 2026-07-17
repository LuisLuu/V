import asyncio
import json
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from v_core.domains.orchestration.state_machine import run_cognitive_graph

router = APIRouter()

@router.get("/stream_response")
async def stream_response(request: Request, prompt: str):
    """
    Streams the execution status and final synthesis tokens to the client.
    Treats the agent's operations like an observable microservice pipeline.
    """
    queue = asyncio.Queue()
    
    # Fire the cognitive graph as a background task
    graph_task = asyncio.create_task(run_cognitive_graph(prompt, queue))
    
    async def event_generator():
        try:
            while True:
                # Disconnect check to prevent zombie processes
                if await request.is_disconnected():
                    graph_task.cancel()
                    break
                    
                msg = await queue.get()
                yield json.dumps(msg)
                
                if msg["type"] == "done":
                    break
        except asyncio.CancelledError:
            pass # Fails gracefully if the user drops connection
            
    return EventSourceResponse(event_generator())