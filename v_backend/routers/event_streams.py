import asyncio
import json
import aiohttp
import traceback
import re

from fastapi import APIRouter, Request, BackgroundTasks
from agents.orchestration.state_machine import run_cognitive_graph
from memory.sqlite_rom import SQLiteROM
from typing import Optional
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agents.orchestration.auth_registry import auth_registry

router = APIRouter()
rom_db = SQLiteROM()

class AuthPayload(BaseModel):
    action_id: str
    approved: bool

async def generate_session_title(session_id: str, first_prompt: str, queue: Optional[asyncio.Queue] = None):
    """Background task to generate and save a session title, then notify frontend."""
    
    system_instruction = (
        "You are a title generator. Read the user's prompt and summarize it into "
        "a concise, 3 to 4 word title. Respond ONLY with the title. No punctuation, "
        "no quotes, no conversational filler."
    )
    
    # Use a faster timeout for the background namer so it fails quietly and quickly
    FAST_TIMEOUT = aiohttp.ClientTimeout(sock_connect=5, sock_read=15)
    
    try:
        async with aiohttp.ClientSession(timeout=FAST_TIMEOUT) as session:
            async with session.post("http://localhost:11434/api/chat", json={
                "model": "llama3", 
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": first_prompt}
                ],
                "stream": False
            }) as response:
                
                if response.status != 200:
                    print(f"[ERROR] Ollama returned status: {response.status}")
                    return
                    
                result = await response.json()
                title = result["message"]["content"]
        
        clean_title = title.strip(' "\'\n')
        
        # Save to database
        rom_db.update_session_title(session_id, clean_title)
        print(f"[SYSTEM] Session {session_id} auto-named: {clean_title}")
        
        # Inject the new title directly into the SSE stream
        if queue:
            await queue.put({"type": "title_update", "title": clean_title})
            
    except asyncio.TimeoutError:
        print(f"[ERROR] Auto-naming timed out for {session_id}. Engine unresponsive.")
    except Exception as e:
        print(f"[ERROR] Auto-naming failed for {session_id}: {e}")
# -----------------------------------------------------

@router.get("/stream_response")
async def stream_response(
    request: Request, 
    prompt: str, 
    background_tasks: BackgroundTasks, 
    session_id: str = "default_user"
):
    """
    Streams response tracking conversation context histories via ROM.
    """
    queue = asyncio.Queue()
    
    db_history = rom_db.get_recent_context(session_id, limit=10)
    chat_history = [{"role": msg["role"], "content": msg["content"]} for msg in db_history]
    
    # Trigger auto-naming if history is empty and pass the queue
    if not db_history:
        asyncio.create_task(generate_session_title(session_id, prompt, queue))
    
    rom_db.save_message(session_id, "user", prompt)
    
    graph_task = asyncio.create_task(run_cognitive_graph(prompt, queue, chat_history))
    
    async def event_generator():
        v_response = ""
        
        logs = [] 
        try:
            while True:
                if await request.is_disconnected():
                    graph_task.cancel()
                    break
                    
                # THE FIX: Micro-polling to prevent infinite hangs if the graph task dies silently
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    if graph_task.done():
                        exc = graph_task.exception()
                        if exc is not None:
                            raise exc
                        # If task is done but has no exception, and the queue is empty, exit cleanly.
                        print("\n[DEBUG] The graph task finished cleanly but the queue is empty. Closing stream.\n")
                        break 
                        
                    # THE FIX: Send an invisible heartbeat ping to keep the browser socket alive
                    yield ": ping\n\n"
                    continue

                content_str = msg.get("content", "")
                
                # Fuzzy match: catches MEMORY_DRAFT with or without underscores/spaces
                draft_match = re.search(r'(?:__)?MEMORY_DRAFT(?:__)?\s*:\s*(.*)', content_str if isinstance(content_str, str) else "", re.IGNORECASE)
                
                if draft_match:
                    draft_text = draft_match.group(1).strip()
                    
                    # Hijack and rewrite the message payload for the frontend
                    msg = {
                        "type": "memory_draft",
                        "content": draft_text
                    }
                # ---------------------------------------------
                    
                # SSE-Starlette defaults to 'message' events when yielding strings
                yield f"data: {json.dumps(msg)}\n\n"
                
                # Collect status lines as they come in
                if msg["type"] == "status":
                    logs.append(msg.get("content", ""))
                
                # Accumulate tokens for final response
                if msg["type"] == "token":
                    v_response += msg.get("content", "")
                
                if msg["type"] == "done":
                    # Save both response and serialized logs to ROM
                    rom_db.save_message(session_id, "assistant", v_response, logs=json.dumps(logs))
                    break

        except Exception as e:
            print("\n[--- INVISIBLE ERROR CAUGHT ---]")
            traceback.print_exc()  # This prints the raw, bloody error to your console
            print("[------------------------------]\n")
            
            error_msg = str(e)
            if "timed out" in error_msg.lower():
                payload = {"error": "Engine timeout: V's cognitive core took too long to respond. The connection was severed to prevent a system hang."}
            else:
                payload = {"error": f"System Exception: {error_msg}"}
            
            yield f"event: error\ndata: {json.dumps(payload)}\n\n"
            
        except asyncio.CancelledError:
            pass

        # ---> THIS IS THE MISSING PIECE <---
    # Return the generator wrapped in a StreamingResponse with the strict MIME type
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )

@router.post("/api/authorize_command")
async def authorize_command(payload: AuthPayload):
    """
    Receives frontend approval, unlocks the state machine's Blast Gate, 
    and signals the orchestrator to resume.
    """
    # This reaches into the registry and flips the event.set() lock
    success = auth_registry.resolve_action(payload.action_id, payload.approved)
    
    if success:
        print(f"[BLAST GATE] Action {payload.action_id} resolved (Approved: {payload.approved}).")
        return {"status": "resumed" if payload.approved else "denied"}
    
    return {"status": "error", "message": "Action ID expired or not found."}
