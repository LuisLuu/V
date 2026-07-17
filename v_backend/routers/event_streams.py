import asyncio
import json
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from v_core.domains.orchestration.state_machine import run_cognitive_graph

router = APIRouter()

@router.get("/stream_response")
async def stream_response(request: Request, prompt: str, history: str = "[]"):
    """
    Streams response tracking conversation context histories.
    """
    queue = asyncio.Queue()
    
    try:
        chat_history = json.loads(history)
    except Exception:
        chat_history = []
        
    graph_task = asyncio.create_task(run_cognitive_graph(prompt, queue, chat_history))
    
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    graph_task.cancel()
                    break
                    
                msg = await queue.get()
                yield json.dumps(msg)
                
                if msg["type"] == "done":
                    break
        except asyncio.CancelledError:
            pass
            
    return EventSourceResponse(event_generator())