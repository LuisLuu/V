import asyncio
import requests
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict
from agents.orchestration.state_machine import run_cognitive_graph
from memory.ram_window import RAMWindow
from memory.sqlite_rom import SQLiteROM
from agents.compaction import CompactionEngine
from agents.tools.system.task_agent import TaskAgent

api_router = APIRouter()
task_router = APIRouter(prefix="/api/tasks", tags=["tasks"])
agent = TaskAgent()

# 1. INITIALIZE DB FIRST
rom_db = SQLiteROM()

# 2. DEFINE THE SYNC CLIENT BLUEPRINT BEFORE USING IT
class SyncOllamaClient:
    """A dedicated synchronous client for the background CompactionEngine."""
    def __init__(self, model="llama3", url="http://localhost:11434/api/generate"):
        self.model = model
        self.url = url

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json"  
        }
        try:
            response = requests.post(self.url, json=payload, timeout=120)
            if response.status_code == 200:
                return response.json().get("response", "")
            return ""
        except Exception as e:
            print(f"🚨 [Sync LLM Error] {e}")
            return ""
# 3. INITIALIZE ENGINE SECOND
sync_llm = SyncOllamaClient()

# Pass the actual 'rom_db' variable, not the placeholder
compaction_engine = CompactionEngine(rom_connection=rom_db, llm_client=sync_llm)

# 4. THE SESSION MANAGER
active_sessions: Dict[str, RAMWindow] = {}


class ChatPayload(BaseModel):
    message: str
    session_id: str  # Now explicitly required to track conversations
    user_auth: Optional[str] = None

def get_or_create_session(session_id: str) -> RAMWindow:
    """Retrieves an active RAM window, or builds one from ROM if it's missing."""
    if session_id not in active_sessions:
        new_window = RAMWindow(max_chars=4000)
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
            stale_messages = ram.extract_for_compaction()
            # Send them to the background queue so the API can return immediately
            bg_tasks.add_task(compaction_engine.compact_messages, stale_messages)
            print(f"[SYSTEM] Offloaded {len(stale_messages)} messages to background compaction.")
        
        return {"v_response": final_response}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SYSTEM_CRASH: {str(e)}")