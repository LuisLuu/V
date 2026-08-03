# Project V - System Architecture Context

## Directory Structure & Core Modules
- **`agents/orchestration/`**: Contains `state_machine.py` (0-1-2-3 cognitive graph pipeline), `v_core.py` (Planner and Synthesizer LLM modules), and `auth_registry.py` (async event locks for HITL).
- **`agents/harness/`**: Contains `blast_gates.py` (security interceptors and risk tiers) and `sensors.py` (bare-metal environment checks).
- **`agents/tools/`**: Encapsulates modular tools inheriting from `BaseTool` (`directory_scanner.py`, `file_reader.py`, `search_api.py`, `web_scraper.py`, `rest_caller.py`, `task_tool.py`, `bypass_tool.py`, and `memory_tool.py`).
- **`agents/compaction.py`**: Background janitor service (`CompactionEngine`) that offloads stale RAM buffer tokens into ROM keyword summaries.
- **`memory/`**: Contains `sqlite_rom.py` (immutable SQLite store with FTS5 full-text indexing, sessions, tasks, and bcrypt auth) and `ram_window.py` (volatile working memory bounds).
- **`v_backend/`**: FastAPI entry point (`main.py`) paired with routers (`event_streams.py`, `chat_routes.py`, `task_routes.py`, `auth_routes.py`, and `settings_router.py`).
- **`static/`**: Vanilla HTML/JS frontend (`index.html`, `app.js`, `styles.css`, `marked.min.js`) communicating via Server-Sent Events (SSE).