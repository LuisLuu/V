from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from memory.sqlite_rom import SQLiteROM

router = APIRouter()
rom = SQLiteROM()

class PINPayload(BaseModel):
    pin: str

@router.get("/status")
async def check_auth_status():
    """Checks if a Master PIN has been set up in the database."""
    with rom._get_connection() as conn:
        cursor = conn.execute("SELECT id FROM system_auth WHERE id = 1")
        exists = cursor.fetchone() is not None
    return {"is_setup": exists}

@router.post("/setup")
async def setup_pin(payload: PINPayload):
    """Sets the Master PIN for the first time."""
    if len(payload.pin) < 4:
        raise HTTPException(status_code=400, detail="PIN must be at least 4 characters.")
    rom.setup_master_pin(payload.pin)
    return {"message": "Master PIN successfully configured."}

@router.post("/verify")
async def verify_pin(payload: PINPayload):
    """Verifies the provided PIN to unlock the UI."""
    is_valid = rom.verify_master_pin(payload.pin)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid Master PIN.")
    return {"message": "Access granted."}