from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from memory.sqlite_rom import SQLiteROM

# Using a prefix keeps the URL paths clean below
router = APIRouter(prefix="/api/settings", tags=["Configuration"])
rom_db = SQLiteROM()

# --- Pydantic Schemas for validation ---
class ContextPayload(BaseModel):
    context: str

class LearnedFactsPayload(BaseModel):
    learned_facts: str

# --- Context Endpoints ---
@router.get("/context")
async def get_context():
    try:
        context = rom_db.get_user_context()
        return {"context": context}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/context")
async def update_context(payload: ContextPayload):
    try:
        rom_db.update_user_context(payload.context)
        return {"status": "success", "message": "Context saved."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# --- Learned Facts Endpoints (Memory Bank) ---
@router.get("/learned_facts")
async def get_learned_facts():
    try:
        facts = rom_db.get_learned_facts()
        return {"learned_facts": facts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/learned_facts")
async def update_learned_facts(payload: LearnedFactsPayload):
    try:
        rom_db.update_learned_facts(payload.learned_facts)
        return {"status": "success", "message": "Memory Bank saved."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")