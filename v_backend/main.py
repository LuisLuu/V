from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os

from v_backend.routers import event_streams, chat_routes 

app = FastAPI()

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(event_streams.router)

# 👇 2. Mount the chat router to a specific API path
app.include_router(chat_routes.api_router, prefix="/api/chat") 

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_path = os.path.join(static_dir, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())