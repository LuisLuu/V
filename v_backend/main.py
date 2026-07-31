import os
import signal
import threading
import time

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
from v_backend.routers import event_streams, chat_routes 
from v_backend.routers.task_routes import task_router
from v_backend.routers import auth_routes
from memory.sqlite_rom import SQLiteROM

# Instantiate a global DB connection for our API routes
db = SQLiteROM()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs the moment you type `uvicorn v_backend.main:app --reload`
    print("🚀 Booting V Backend... Running memory maintenance.")
    prune_old_memories = getattr(db, "prune_old_memories", None)
    if callable(prune_old_memories):
        prune_old_memories(days=3)
    yield

app = FastAPI(lifespan=lifespan)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(event_streams.router)
app.include_router(chat_routes.api_router, prefix="/api/chat") 
app.include_router(task_router)
app.include_router(auth_routes.router, prefix="/api/auth")

# --- NEW SESSION ROUTES ---
@app.post("/api/sessions/")
async def create_new_session():
    # Defers the intelligent LLM naming to a background task later; keeps the UI fast.
    session_id = db.create_session(initial_title="New Chat") 
    return {"session_id": session_id, "title": "New Chat"}

@app.get("/api/sessions/")
async def get_sessions():
    sessions = db.get_all_sessions()
    return {"sessions": sessions}

class SessionUpdate(BaseModel):
    title: str

# Fetch Full Chat History for the UI
@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    messages = db.get_session_history(session_id)
    return {"messages": messages}

# Rename Session (CRUD Update)
@app.patch("/api/sessions/{session_id}")
async def rename_session_route(session_id: str, payload: SessionUpdate):
    db.update_session_title(session_id, payload.title)
    return {"status": "success"}

# Delete Session (CRUD Delete)
@app.delete("/api/sessions/{session_id}")
async def delete_session_route(session_id: str):
    db.delete_session(session_id)
    return {"status": "success"}

@app.post("/api/shutdown")
async def shutdown_server():
    """Forces the Uvicorn server to shut down immediately."""
    print("🛑 [SYSTEM] Shutdown signal received. Terminating V...")
    
    def kill_it():
        time.sleep(0.5) # Give the server half a second to respond to the browser
        os._exit(0)     # Hard kill the Python process
        
    threading.Thread(target=kill_it).start()
    return {"status": "shutting down"}

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_path = os.path.join(static_dir, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
