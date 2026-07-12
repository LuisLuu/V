# v_backend/routers/event_streams.py
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
import json

router = APIRouter()

# In a real app, this queue would be tied to a specific user's active session ID
# For this implementation, we use a global queue to bridge the Orchestrator to the HTTP layer
execution_queue = asyncio.Queue()

async def event_generator(request: Request):
    """
    Yields real-time execution states from the Orchestrator to the frontend.
    Disconnects cleanly if the client drops.
    """
    try:
        while True:
            # If the client disconnects, break the loop to free memory
            if await request.is_disconnected():
                break
                
            # Wait for the next event from the Orchestrator
            event_data = await execution_queue.get()
            
            # Format according to SSE standard: "data: {json}\n\n"
            yield f"data: {json.dumps(event_data)}\n\n"
            
            # If we hit a blast gate or task completion, signal the frontend to stop waiting
            if event_data.get("status") in ["SYSTEM_HALT", "COMPLETED"]:
                break
                
    except asyncio.CancelledError:
        pass

@router.get("/stream")
async def stream_orchestrator_events(request: Request):
    """
    The endpoint the React frontend will subscribe to via EventSource.
    """
    return StreamingResponse(event_generator(request), media_type="text/event-stream")