import os
from typing import Generator
from agents.router import MemoryRouter

# Robust path resolution: Pinpoint 'data/rom.db' relative to this file's location.
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
DB_PATH = os.path.join(PROJECT_ROOT, "data", "rom.db")

def get_memory_router() -> Generator[MemoryRouter, None, None]:
    """
    Dependency injection for the Memory Router.
    The MemoryRouter manages its own stateless SQLite connections via context managers.
    """
    router = MemoryRouter(db_path=DB_PATH)
    yield router