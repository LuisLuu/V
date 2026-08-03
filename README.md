V - The AI AssistantA Deterministic, Compound AI System for Local Desktop AutomationAuthor: Lưu Trương Thế Quyền  Institution: University of Greenwich  Program: BSc (Hons) Computing  

📖 Project OverviewStandard ReAct (Reason + Act) LLM architectures frequently fail in production due to compounding errors and "context rot," where monolithic context windows distract model focus and cause hallucinations.  Project V addresses these weaknesses by replacing fragile single-agent loops with a deterministic, Compound AI System. V isolates operational functions into specialized sub-agents, enforces strict graph-based progression, and wraps tool execution in a secure Human-in-the-Loop (HITL) harness.  

✨ Core Architectural Features

Two-Tier Memory System (SQLiteROM & RAMWindow): Combines a volatile short-term RAM buffer with an immutable SQLite database (ROM) supporting Write-Ahead Logging (WAL). A background CompactionEngine offloads stale tokens into keyword-indexed summaries, while MemoryRouter uses SQLite FTS5 full-text indexing for dynamic context recall.  

Human-in-the-Loop (HITL) Blast Gates (BlastGate & AuthRegistry): Secures local environments by categorizing tool actions into READ, WRITE, and DESTRUCTIVE security tiers. Dangerous or destructive operations halt the execution engine using asyncio.Event locks, prompting the user for explicit web UI authorization.  

Graph-Based Cognitive Orchestration (state_machine.py & VCore): Replaces unpredictable LLM loops with a deterministic 0-1-2-3 pipeline (Context Routing -> Planning -> Execution -> Synthesis) validated via Pydantic schemas.  

Fully Local & Private Inference: Powered entirely by local models running on Ollama (http://localhost:11434), guaranteeing absolute data privacy and offline operational capability.  

🏛️ Codebase Architecture & Modules1. 

1. The Cognitive Engine (agents/orchestration/)

state_machine.py: Enforces the strict cognitive graph pipeline, handles sanitization of historical chat logs, sandboxes asynchronous tool execution, and manages HITL pauses.  

v_core.py: Splits cognitive processing into isolated Planner and Synthesizer LLM modules communicating via aiohttp.  

2. Security & Harness (agents/harness/)

blast_gates.py: Acts as the central security interceptor evaluating tool risk tiers before execution.  

sensors.py: Verifies OS compatibility, network connectivity, and directory-based workspace isolation.  

3. Persistent & Working Memory (memory/)

sqlite_rom.py: Manages the core SQLite database (rom.db), FTS5 virtual indexing triggers, session management, task ledgers, bcrypt master PIN verification, and autonomous dynamic memory banks.  

ram_window.py: Tracks working memory bounds by character weight and triggers compaction when capacity becomes critical.  

router.py (MemoryRouter): Extracts stop-word-filtered keywords from prompts to query FTS5 chat search indexes using dynamic relative thresholding.  

4. Tool Registry & Sub-Agents (agents/tools/)

Filesystem & System Tools: DirectoryScanner, FileReader, CommandExecutor, and TaskManagerTool (TaskAgent).  

Web & Network Tools: SearchAPI (DuckDuckGo Lite snippet extractor), WebScraper, and RESTCaller.  

System Control: ConversationalBypass and MemoryDraftTool for automated third-person user preference capture. 

5. Backend Server (v_backend/)

main.py: Initializes the FastAPI application, background lifespan tasks, static file mounts, and graceful shutdown sequences.  

Routers: Modular endpoints handling real-time Server-Sent Events (event_streams.py), chat sessions (chat_routes.py), task CRUD (task_routes.py), PIN authentication (auth_routes.py), and configuration (settings_router.py).  

6. Frontend Interface (static/)
index.html, app.js, styles.css: A responsive 3-column reactive interface built with Vanilla JavaScript and marked.js supporting real-time token streaming, process log inspection, session management, task sidebars, and secure PIN unlocking.

🛠️ Technology StackBackend: 
Python, FastAPI, Uvicorn, Pydantic, AIOHTTP, Bcrypt  

AI / Inference Engine: Local Ollama (llama3)  

Database & Indexing: SQLite (ROM, Sessions, Tasks, System Auth, Dynamic Memory) with FTS5 Full-Text Search  

Frontend: Vanilla HTML5, CSS3, JavaScript, Server-Sent Events (SSE), Marked.js  

🚀 Quick Start Guide (Examiner-Proof Setup)
V is designed to run locally with automated environment configuration.

PrerequisitesPython 3.10+  
Ollama installed and active locally (http://localhost:11434)  

Windows
Open the project root folder.  
Double-click the start_windows.bat file.  
The script creates the virtual environment, installs dependencies from requirements.txt, verifies Ollama, and launches the V Desktop Interface in your browser.  

Mac / Linux
Open your terminal and navigate to the project root.  
Grant execution permissions: chmod +x start_unix.sh  Run the launcher: ./start_unix.sh  