import asyncio
import json
import aiohttp
from fastapi import APIRouter, Request, BackgroundTasks
from sse_starlette.sse import EventSourceResponse
from agents.orchestration.state_machine import run_cognitive_graph
from memory.sqlite_rom import SQLiteROM

router = APIRouter()
rom_db = SQLiteROM()

async def generate_session_title(session_id: str, first_prompt: str, queue: asyncio.Queue = None):
    """Background task to generate and save a session title, then notify frontend."""
    
    system_instruction = (
        "You are a title generator. Read the user's prompt and summarize it into "
        "a concise, 3 to 4 word title. Respond ONLY with the title. No punctuation, "
        "no quotes, no conversational filler."
    )
    
    try:
        async with aiohttp.ClientSession() as session:
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
                    
                msg = await queue.get()
                yield json.dumps(msg)
                
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
        except asyncio.CancelledError:
            pass
            
    return EventSourceResponse(event_generator())