from fastapi import FastAPI
from v_backend.routers import event_streams, chat_routes

app = FastAPI(title="V Cognitive API", description="Central network bridge for V's ReAct loop.")

# Mount the SSE stream route
app.include_router(chat_routes.router)

@app.get("/")
def health_check():
    """A simple ping to verify the server is alive."""
    return {"status": "V is online, listening, and awaiting input."}