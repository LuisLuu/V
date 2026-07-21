import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict

from v_core.domains.orchestration.state_machine import run_cognitive_graph
from v_core.domains.memory.ram_window import RAMWindow
from v_core.domains.memory.sqlite_rom import SQLiteROM
from v_core.domains.memory.compaction import CompactionEngine

api_router = APIRouter()

# 1. INITIALIZE DB FIRST
rom_db = SQLiteROM()

# 2. INITIALIZE ENGINE SECOND (Passing None for llm_client temporarily)
compaction_engine = CompactionEngine(rom_connection=rom_db, llm_client=None) 

# 3. THE SESSION MANAGER
active_sessions: Dict[str, RAMWindow] = {}

class ChatPayload(BaseModel):
    message: str
    session_id: str  # Now explicitly required to track conversations
    user_auth: Optional[str] = None

def get_or_create_session(session_id: str) -> RAMWindow:
    """Retrieves an active RAM window, or builds one from ROM if it's missing."""
    if session_id not in active_sessions:
        new_window = RAMWindow(capacity=10)
        past_context = rom_db.get_recent_context(session_id, limit=5)
        
        for msg in past_context:
            # Now passing row_id dynamically from the database
            new_window.add_interaction(role=msg["role"], content=msg["content"], row_id=msg["id"])
            
        active_sessions[session_id] = new_window
        print(f"[SYSTEM] Spun up new RAMWindow for session: {session_id}")
        
    return active_sessions[session_id]

@api_router.post("/")
async def talk_to_v(payload: ChatPayload, bg_tasks: BackgroundTasks):
    if not payload.message or not payload.session_id:
        raise HTTPException(status_code=400, detail="Payload requires 'message' and 'session_id'.")

    try:
        ram = get_or_create_session(payload.session_id)
        
        # 1. Save user message to ROM & RAM
        user_row_id = rom_db.save_message(payload.session_id, "user", payload.message)
        ram.add_interaction("user", payload.message, row_id=user_row_id)
        
        # 2. Run the graph (same as before)
        yield_queue = asyncio.Queue()
        chat_history = ram.buffer 
        
        graph_task = asyncio.create_task(run_cognitive_graph(payload.message, yield_queue, chat_history))
        final_response = ""
        
        while True:
            item = await yield_queue.get()
            if item["type"] == "done":
                break
            elif item["type"] == "token":
                final_response += item["content"]

        await graph_task
        
        # 3. Save V's response to ROM & RAM
        assistant_row_id = rom_db.save_message(payload.session_id, "assistant", final_response)
        ram.add_interaction("assistant", final_response, row_id=assistant_row_id)
        
        # 4. Trigger Background Compaction if Critical
        if ram.is_critical:
            # Instantly remove the oldest 4 messages from active RAM
            stale_messages = ram.extract_for_compaction(count=4)
            # Send them to the background queue so the API can return immediately
            bg_tasks.add_task(compaction_engine.compact_messages, stale_messages)
            print(f"[SYSTEM] Offloaded {len(stale_messages)} messages to background compaction.")
        
        return {"v_response": final_response}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SYSTEM_CRASH: {str(e)}")