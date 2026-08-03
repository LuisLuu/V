from contextlib import asynccontextmanager
import os
import signal
import threading
import time

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from memory.sqlite_rom import SQLiteROM
from v_backend.routers import auth_routes, chat_routes, event_streams, settings_router
from v_backend.routers.task_routes import task_router

# Instantiate a global DB connection for our API routes[cite: 31]
db = SQLiteROM()


class ContextUpdate(BaseModel):
    context: str


class SessionUpdate(BaseModel):
    title: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs the moment you type `uvicorn v_backend.main:app --reload`[cite: 31]
    print("🚀 Booting V Backend... Running memory maintenance.")
    prune_old_memories = getattr(db, "prune_old_memories", None)
    if callable(prune_old_memories):
        prune_old_memories(days=3)
    yield


app = FastAPI(lifespan=lifespan)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include Routers[cite: 31]
app.include_router(event_streams.router)
app.include_router(chat_routes.api_router, prefix="/api/chat")
app.include_router(task_router)
app.include_router(auth_routes.router, prefix="/api/auth")
app.include_router(settings_router.router)


@app.get("/")
async def serve_frontend():
    return FileResponse(os.path.join(static_dir, "index.html"))


# --- SESSION ROUTES ---
@app.post("/api/sessions/")
async def create_new_session():
    # Defers the intelligent LLM naming to a background task later; keeps the UI fast.[cite: 31]
    session_id = db.create_session(initial_title="New Chat")
    return {"session_id": session_id, "title": "New Chat"}


@app.get("/api/sessions/")
async def get_sessions():
    sessions = db.get_all_sessions()
    return {"sessions": sessions}


@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    messages = db.get_session_history(session_id)
    return {"messages": messages}


@app.patch("/api/sessions/{session_id}")
async def rename_session_route(session_id: str, payload: SessionUpdate):
    db.update_session_title(session_id, payload.title)
    return {"status": "success"}


@app.delete("/api/sessions/{session_id}")
async def delete_session_route(session_id: str):
    db.delete_session(session_id)
    return {"status": "success"}


# --- SETTINGS & CONTEXT ROUTES ---
@app.get("/api/settings/context")
async def get_user_context_route():
    context = db.get_user_context()
    return {"context": context}


@app.post("/api/settings/context")
async def update_user_context_route(payload: ContextUpdate):
    db.update_user_context(payload.context)
    return {"status": "success"}


# --- MEMORY ROUTES ---
@app.get("/api/memory")
async def get_memory_route():
    facts_str = db.get_learned_facts(limit=50)
    return {"facts": facts_str}


@app.post("/api/memory")
async def update_memory_route(payload: dict):
    db.save_learned_facts_bulk(payload.get("facts", ""))
    return {"status": "success"}


# --- SYSTEM TERMINATION ---
@app.post("/api/shutdown")
def shutdown():
    print(
        "🛑 [SYSTEM] Shutdown signal received. Initiating full termination sequence..."
    )

    def kill_server():
        # 1. Give FastAPI half a second to return the 200 OK to your UI[cite: 31]
        time.sleep(0.5)

        # 2. Grab the Parent Process ID (the Uvicorn reloader)[cite: 31]
        parent_pid = os.getppid() if hasattr(os, "getppid") else os.getpid()

        try:
            # 3. Terminate the parent reloader first, then the child worker[cite: 31]
            os.kill(parent_pid, signal.SIGTERM)
            if parent_pid != os.getpid():
                os.kill(os.getpid(), signal.SIGTERM)
        except Exception:
            # 4. The Brute-Force Fallback: If signals fail, aggressively drop the process[cite: 31]
            os._exit(0)

    # Launch the kill sequence in the background[cite: 31]
    threading.Thread(target=kill_server).start()

    return {"message": "V Engine Terminated."}


# uvicorn v_backend.main:app --host 127.0.0.1 --port 8000