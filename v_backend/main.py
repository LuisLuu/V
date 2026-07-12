from fastapi import FastAPI
from v_backend.routers import event_streams, chat_routes

app = FastAPI(title="Project V", version="0.2.0")

# Mount the SSE stream route
app.include_router(event_streams.router, prefix="/api/events", tags=["Streaming"])
# app.include_router(chat_routes.router, prefix="/api/chat", tags=["Chat"])

@app.get("/health")
def health_check():
    return {"status": "Operational", "sandbox": "Locked"}