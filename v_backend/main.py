from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from v_backend.routers import event_streams, chat_routes
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

app = FastAPI(title="V Cognitive API")

# Mount the SSE stream route
app.include_router(chat_routes.router)
app.include_router(event_streams.router)

# Mount the frontend directory.
app.mount("/", StaticFiles(directory="v_backend/static", html=True), name="static")