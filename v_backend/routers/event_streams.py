import asyncio
import json
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from agents.orchestration.state_machine import run_cognitive_graph
from memory.sqlite_rom import SQLiteROM

router = APIRouter()
rom_db = SQLiteROM()

@router.get("/stream_response")
async def stream_response(request: Request, prompt: str, session_id: str = "default_user"):
    """
    Streams response tracking conversation context histories via ROM.
    """
    queue = asyncio.Queue()
    
    # 1. Fetch clean history directly from the DB instead of the URL
    db_history = rom_db.get_recent_context(session_id, limit=10)
    chat_history = [{"role": msg["role"], "content": msg["content"]} for msg in db_history]
    
    # 2. Save the user's new prompt to ROM
    rom_db.save_message(session_id, "user", prompt)
    
    graph_task = asyncio.create_task(run_cognitive_graph(prompt, queue, chat_history))
    
    async def event_generator():
        v_response = ""
        try:
            while True:
                if await request.is_disconnected():
                    graph_task.cancel()
                    break
                    
                msg = await queue.get()
                yield json.dumps(msg)
                
                # Accumulate the tokens to save the final message
                if msg["type"] == "token":
                    v_response += msg.get("content", "")
                
                if msg["type"] == "done":
                    # 3. Save V's completed response to ROM
                    rom_db.save_message(session_id, "assistant", v_response)
                    break
        except asyncio.CancelledError:
            pass
            
    return EventSourceResponse(event_generator())