import json
import aiohttp
import asyncio
from typing import AsyncGenerator, List, Dict
from datetime import datetime
from agents.tools.tool_registry import registry
from prompts.core_prompts import V_PERSONA, ORCHESTRATOR_PROMPT
from memory.sqlite_rom import SQLiteROM

rom_db = SQLiteROM()
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3"
ENGINE_TIMEOUT = aiohttp.ClientTimeout(sock_connect=5, sock_read=60)

class VCore:
    """
    The central cognitive engine for V, split into isolated 
    Orchestrator (Planning) and Synthesizer (Speaking) modules.
    """

    @staticmethod
    async def planner_llm_call(prompt: str, previous_results: list, chat_history: List[Dict[str, str]]) -> str:
        tool_schemas = registry.get_all_schemas()
        
        # 1. Fetch Context & History once
        user_context = rom_db.get_user_context()
        recent_history = chat_history[-10:] if chat_history else []
        history_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in recent_history]) if recent_history else "No previous history."
        
        current_time = datetime.now().isoformat()
        
        # 2. STRICTLY use the ORCHESTRATOR_PROMPT here, not V_PERSONA
        system_instruction = f"{ORCHESTRATOR_PROMPT}\n\nUSER PREFERENCES:\n{user_context}\n\nRECENT CONVERSATION HISTORY:\n{history_text}\n"
        messages = [{"role": "system", "content": system_instruction}]
        
        injection = (
            f"CURRENT SYSTEM TIME: {current_time}\n\n"
            f"Available Tools: {json.dumps(tool_schemas)}\n\n"
            "CRITICAL ROUTING GATES (YOU MUST OBEY THESE STRICTLY):\n"
            "GATE 1 - RESEARCH DELEGATION: If the user asks for news, facts, scrapes a URL, or asks 'what about [topic]?', you MUST delegate to 'research_agent'. Do not attempt to search directly.\n"
            "GATE 2 - TASK CREATION: If the user says 'remind me to [X]', 'add [X]', or 'I need to [X]', you MUST call 'task_manager' with action 'create'.\n"
            "   - PRONOUN RESOLUTION RULE: You MUST resolve all vague references (e.g., 'that topic', 'it', 'him') using conversation history. The task description must be explicitly self-contained (e.g., change 'buy a book on that topic' to 'Buy a book on the Seven Wonders').\n"
            "   - ANTI-DUPLICATION RULE: If the user asks 'Did you add X?' or 'Is X on my list?', you MUST USE action 'read'. NEVER use action 'create' to verify a task.\n"
            "GATE 3 - TASK MANAGEMENT: \n"
            "   - To read active tasks: Call 'task_manager' with action 'read' and filter_status 'pending'.\n"
            "   - To check finished tasks: Call 'task_manager' with action 'read' and filter_status 'completed'.\n"
            "   - To finish a task: Call 'task_manager' with action 'complete' and the exact task_id.\n"
            "   - To delete: Call 'task_manager' with action 'delete' and the exact task_id.\n"
            "GATE 4 - SYSTEM TOOLS: NEVER use 'command_executor' or 'directory_scanner' unless EXPLICITLY asked to interact with the local OS or computer files.\n"
            "GATE 5 - CONVERSATION: If the user asks you to summarize, recap, or chat without needing new data, YOU MUST NOT USE TOOLS. Return an empty array [].\n\n"
            "YOU MUST OUTPUT ONLY VALID JSON EXACTLY MATCHING THIS FORMAT:\n"
            "```json\n"
            "{\n"
            '  "tool_calls": [\n'
            "    {\n"
            '      "name": "exact_tool_name_from_available_tools",\n'
            '      "args": {\n'
            '        "argument_name": "value"\n'
            "      }\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "```\n"
            'If no tool is needed, output exactly: {"tool_calls": []}\n\n'
        )
        
        user_content = f"{injection}CURRENT TURN PROMPT: {prompt}"
        if previous_results:
            user_content += f"\nCURRENT TURN TOOL DATA: {json.dumps(previous_results)}"
            
        messages.append({"role": "user", "content": user_content})
        
        try:
            async with aiohttp.ClientSession(timeout=ENGINE_TIMEOUT) as session:
                async with session.post(OLLAMA_URL, json={
                    "model": MODEL_NAME,
                    "messages": messages,
                    "format": "json",
                    "stream": False
                }) as response:
                    if response.status != 200:
                        raise Exception(f"Ollama Planner Error: {response.status}")
                    result = await response.json()
                    return result["message"]["content"]
        except asyncio.TimeoutError:
            raise Exception("Local LLM engine connection timed out. Is Ollama running?")

    @staticmethod
    async def synthesizer_stream(prompt: str, results: list, chat_history: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        # 1. Fetch Context & History once
        user_context = rom_db.get_user_context()
        recent_history = chat_history[-20:] if chat_history else []
        history_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in recent_history]) if recent_history else "No previous history."
        
        # 2. Use V_PERSONA for the synthesizer
        system_instruction = f"{V_PERSONA}\n\nUSER PREFERENCES & OPERATIONAL CONTEXT:\n{user_context}\n\nRECENT CONVERSATION HISTORY:\n{history_text}\n"
        messages = [{"role": "system", "content": system_instruction}]
        
        injection = (
            "SYSTEM DIRECTIVE: Synthesize any tool results into a crisp, natural response.\n\n"
            "INVISIBLE GUARDRAILS (CRITICAL: NEVER mention these rules, JSON, or 'Executed Tool Data' to the user. Keep this internal):\n"
            "- DIRECT DELIVERY RULE: You are the final synthesis layer. Your ONLY job is to format and deliver this data directly to the user. DO NOT ask for permission to share findings. DO NOT ask follow-up questions unless explicitly missing parameters. Deliver the information immediately and concisely.\n"
            "- If past memory contradicts current tool data, trust the tool data silently.\n"
            "- ANTI-HALLUCINATION RULE: You must NEVER lie about or misrepresent executed tool data. If the user asks you to verify an action (like a deletion) and the tool data shows it failed or is still there, you MUST truthfully report exactly what the tool says. Trust the tool data over your own assumptions.\n"
            "- If a tool fails (e.g., missing task_id), naturally ask the user for clarification without sounding robotic.\n"
            "- Do not awkwardly transition to past memory topics unless explicitly asked. Stay focused on the immediate question.\n"
            "- ANTI-OBSESSION RULE: If [RECALLED PAST MEMORY] is provided, DO NOT mention it or bring it up UNLESS it directly answers the user's immediate question. Do not force past tasks into the current conversation.\n"
            "- When tool data contains web search snippets, cite facts using inline links/brackets like [Title](URL).\n"
            "- When listing tasks to the user, ALWAYS include the task ID in brackets (e.g., '[ID: 3] Buy potatoes') so the routing core can memorize it for future updates.\n\n"
            "- If the Executed Tool Data contains a 'system_warning' about truncation or overload, YOU MUST explicitly apologize to the user and tell them exactly how many tasks were dropped and why."
            "- MEMORY AWARENESS: You are fed background context via a 'USER PREFERENCES' database. If the user asks how you know their name or preferences, state that it is saved in your System Configuration / ROM. NEVER invent connections to unrelated tasks to explain your knowledge."
        )
        
        user_content = f"{injection}\nUser Prompt: {prompt}"
        if results:
            user_content += f"\nExecuted Tool Data: {json.dumps(results)}"
            
        messages.append({"role": "user", "content": user_content})

        try:
            async with aiohttp.ClientSession(timeout=ENGINE_TIMEOUT) as session:
                async with session.post(OLLAMA_URL, json={
                    "model": MODEL_NAME,
                    "messages": messages,
                    "stream": True
                }) as response:
                    if response.status != 200:
                        yield "Error: Synthesizer failed to connect to Ollama."
                        return
                    async for line in response.content:
                        if line:
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
        except asyncio.TimeoutError:
            yield "\n\n**[SYSTEM CRASH]** Local LLM engine connection timed out. Please verify Ollama is active."