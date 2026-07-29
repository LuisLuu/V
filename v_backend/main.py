import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from v_backend.routers import event_streams, chat_routes 
from v_backend.routers.task_routes import task_router
from fastapi import FastAPI
from contextlib import asynccontextmanager
from memory.sqlite_rom import SQLiteROM

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. This runs the moment you type `uvicorn v_backend.main:app --reload`
    print("🚀 Booting V Backend... Running memory maintenance.")
    rom = SQLiteROM()
    prune_old_memories = getattr(rom, "prune_old_memories", None)
    if callable(prune_old_memories):
        prune_old_memories(days=3)
    
    yield

app = FastAPI(lifespan=lifespan)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(event_streams.router)
app.include_router(chat_routes.api_router, prefix="/api/chat") 
app.include_router(task_router)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_path = os.path.join(static_dir, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())