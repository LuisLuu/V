import os
from pathlib import Path
from data.sqlite_rom import SQLiteROM

def bootstrap_database():
    # Define the strict, root-level data vault
    db_dir = Path("data")
    db_path = db_dir / "rom.db"

    # Create the data directory if it doesn't exist
    db_dir.mkdir(parents=True, exist_ok=True)

    # Instantiating the class automatically fires _init_db() and builds the schema
    print(f"Initializing database at {db_path.resolve()}...")
    rom = SQLiteROM(db_path=str(db_path))
    
    print("Database compiled successfully. Ready for operations.")

if __name__ == "__main__":
    bootstrap_database()