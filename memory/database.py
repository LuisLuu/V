from pathlib import Path
from memory.sqlite_rom import SQLiteROM

def bootstrap_database():
    # Point directly to the hardcoded memory directory
    memory_dir = Path(__file__).resolve().parent / "memory"
    db_path = memory_dir / "rom.db"

    print(f"Initializing database at {db_path}...")
    
    # Instantiating the class automatically fires _init_db() and builds the schema
    rom = SQLiteROM()
    
    print("Database compiled successfully. Ready for operations.")

if __name__ == "__main__":
    bootstrap_database()