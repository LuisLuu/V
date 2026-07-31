Let’s get this finalized. Your README is the absolute front door to your project. Much like executing a major cleanup of a living space to clear out accumulated clutter, a pristine, well-structured README strips away the technical noise and invites the examiner into a perfectly organized, highly functional environment. If the README is messy, they will assume the code is messy before they even run it.

Since we pivoted to the one-click startup scripts and excised the IoT hardware, your documentation needs to reflect this streamlined, software-first Compound AI architecture.

Here is a comprehensive, brutally professional README.md template tailored exactly for your university submission. Copy this directly into your repository.

V - The AI Assistant
A Deterministic, Compound AI System for Local Desktop Automation

Author: Luu Truong The Quyen

Institution: University of Greenwich

Program: BSc (Hons) Computing

📖 Project Overview
Autonomous AI agents often fail in production environments due to the inherent probabilistic nature of Large Language Models (LLMs). Standard ReAct (Reason + Act) architectures are highly susceptible to compounding errors and "context rot," where monolithic context windows distract the model's focus, leading to confident but incorrect outputs (hallucinations).

Project V addresses these critical weaknesses by shifting from a fragile single-agent model to a deterministic, Compound AI System. V isolates functions into specialized sub-agents, enforces progressive context disclosure, and wraps tool execution in a strict Human-in-the-Loop (HITL) security harness.

✨ Core Architectural Features
Two-Tier Memory System: Mitigates context rot by combining a volatile short-term RAM buffer with a reversible memory compaction engine that archives semantic summaries into an SQLite ROM.

Human-in-the-Loop (HITL) Blast Gates: Secures the local environment by categorizing tool actions into Risk Tiers. Destructive actions (e.g., shell execution, database deletion) halt the state machine and require explicit user authorization.

Graph-Based Orchestration: Replaces unpredictable LLM loops with a rigid state machine that routes tasks to specialized agents (Task Manager, Web Search, System Executor) based on verified intents.

Fully Local & Private Inference: Powered entirely by local models via Ollama, ensuring zero data leakage and offline availability.

🚀 Quick Start Guide (Examiner-Proof Setup)
V is designed to run locally with zero manual dependency wrestling. The provided startup scripts will automatically check your Python environment, verify/install Ollama, boot the background server, pull the required local LLM, and launch the application.

Prerequisites
Python 3.10+

Optional but recommended: An OpenAI/Anthropic API key in a .env file for enhanced external routing (the script will warn you if it is missing, but will still attempt to proceed with local fallback).

Windows
Open the project root folder.

Double-click the start_windows.bat file.

The script will automatically create a virtual environment, install dependencies, prepare Ollama, and launch the V Desktop Interface in your browser.

Mac / Linux
Open your terminal and navigate to the project root.

Ensure the script has execution permissions: chmod +x start_unix.sh

Run the launcher: ./start_unix.sh

The system will handle environment setup and open the reactive UI.

🖥️ System Interface & Modules
The V Desktop Agent features a low-latency, reactive interface built with Vanilla HTML/CSS/JS (Server-Sent Events) to ensure absolute observability of the AI's internal state.

Home (Chat UI): The primary conversational interface. Features real-time token streaming, tool execution indicators, and modal pop-ups for HITL security prompts.

Dashboard: A live telemetry view displaying system health, RAM vs. Context usage, and active orchestration states.

Task Manager: A reactive CRUD interface for the SQLite tasks database, allowing manual manipulation of agent-generated tasks and deadlines.

Memory Explorer: An audit trail interface to view compacted ROM archives and trace the semantic lineage of any active task back to its original conversational prompt.

🛠️ Technology Stack
Backend: Python, FastAPI, Uvicorn (Asynchronous Event-Driven Routing)

AI / Inference: Ollama (Local), OpenAI/Anthropic APIs (Cloud Fallback)

Database: SQLite (Structured ROM & Task Ledger), ChromaDB (Semantic Vector Search)

Frontend: Vanilla HTML5, CSS3, JavaScript (SSE integration, marked.js)

📚 Academic Documentation
For a deep dive into the architectural design, compounding error mitigation strategies, and system evaluation, please refer to the formal project report included in this repository:
📄 Report_LuuTruongTheQuyen.pdf