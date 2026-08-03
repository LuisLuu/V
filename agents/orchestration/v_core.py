import json
import aiohttp
import asyncio
import platform

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
        print("\n[DEBUG] --- ENTERED PLANNER_LLM_CALL ---")
        
        # --- THE TRAP ---
        try:
            tool_schemas = registry.get_all_schemas()
        except Exception as e:
            print(f"\n[CRITICAL REGISTRY ERROR]: {str(e)}")
            raise
        
        print("[DEBUG] Fetching context from ROM DB...")
        # Synchronous SQLite read to prevent cross-thread crashes
        user_context = rom_db.get_user_context()
        learned_facts = rom_db.get_learned_facts()
        print("[DEBUG] ROM fetch complete. Building payload...")
        
        recent_history = chat_history[-10:] if chat_history else []
        history_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in recent_history]) if recent_history else "No previous history."
        
        current_time = datetime.now().isoformat()
        current_os = platform.system()
        
        system_instruction = f"{ORCHESTRATOR_PROMPT}\n\n[SYSTEM ROM: USER PREFERENCES & CONTEXT]:\n{user_context}\n\n[SYSTEM ROM: AUTONOMOUS MEMORY BANK]:\n{learned_facts}\n\n..."
        messages = [{"role": "system", "content": system_instruction}]
        
        injection = (
            f"CURRENT SYSTEM TIME: {current_time}\n\n"
            f"!!! CRITICAL SYSTEM ARCHITECTURE !!!\n"
            f"You are operating on a {current_os} machine. If you use Gate 7 (BARE-METAL CODE EXECUTION) or write any scripts, they MUST be strictly compatible with {current_os}. Failure to use native {current_os} commands will crash the system.\n\n"
            f"Available Tools: {json.dumps(tool_schemas)}\n\n"
            "CRITICAL ROUTING GATES (YOU MUST OBEY THESE STRICTLY IN ORDER):\n"
            "GATE 1 - MEMORY DRAFTING (HIGHEST PRIORITY): If the user shares a personal fact, habit, physical limitation, or preference, YOU MUST call 'draft_memory_update'.\n"
            "CRITICAL PERSPECTIVE RULE: You MUST translate the fact into third-person starting with 'User' (e.g., convert 'I am allergic to peanuts' -> 'User is allergic to peanuts').\n"
            "GATE 2 - SYSTEM TOOLS (COMMANDS): NEVER use 'command_executor' or 'directory_scanner' unless EXPLICITLY asked to interact with the local OS or computer files. CRITICAL CONSTRAINT: If the command is to 'remember' a fact, DO NOT use this gate; you MUST fall back to Gate 1.\n"
            "GATE 3 - TASK CREATION: If the user says 'remind me to [X]', 'add [X]', or 'I need to [X]', you MUST call 'task_manager' with action 'create'.\n"
            "   - PRONOUN RESOLUTION RULE: You MUST resolve all vague references using conversation history.\n"
            "   - ANTI-DUPLICATION RULE: If verifying a task, use action 'read', not 'create'.\n"
            "GATE 4 - TASK MANAGEMENT: To read, complete, or delete active tasks using 'task_manager'.\n"
            "GATE 5 - WEB SEARCH (RESTRICTED): If the user EXPLICITLY asks for external news, real-time facts, or internet data, use 'search_api'. NEVER use this tool to look up user data, schedules, or local files. Local data is strictly accessed via Gate 2.\n"
            "GATE 6 - CONVERSATION: If the user is just chatting, sharing a story, or making casual conversation. CRITICAL CONSTRAINT: Scan the text first. If the user mentions a persistent personal fact (even casually), YOU MUST route to Gate 1 instead. Otherwise, return an empty array [].\n\n"
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
        
        print(f"\n[DEBUG] Planner payload compiled. Prompt length: {len(user_content)} chars")
        
        try:
            async with aiohttp.ClientSession(timeout=ENGINE_TIMEOUT) as session:
                print("[DEBUG] aiohttp session opened. Sending POST to Ollama...")
                payload = {
                    "model": MODEL_NAME,
                    "messages": messages,
                    "format": "json", 
                    "stream": False
                }
                async with session.post(OLLAMA_URL, json=payload) as response:
                    print(f"[DEBUG] Ollama responded with status code: {response.status}")
                    if response.status != 200:
                        raise Exception(f"Ollama Planner Error: {response.status}")
                    result = await response.json()
                    print("[DEBUG] JSON extracted successfully.")
                    return result["message"]["content"]
        except asyncio.TimeoutError:
            print("[CRITICAL] aiohttp timed out waiting for Ollama.")
            raise Exception("Local LLM engine connection timed out. Is Ollama running?")
        except Exception as e:
            print(f"[CRITICAL] Unhandled Exception in Planner: {str(e)}")
            raise

    @staticmethod
    async def synthesizer_stream(prompt: str, results: list, chat_history: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        print("\n[DEBUG] --- ENTERED SYNTHESIZER_STREAM ---")
        
        # --- SQLITE CRASH FIX ---
        try:
            user_context = rom_db.get_user_context()
            learned_facts = rom_db.get_learned_facts()
        except Exception as e:
            print(f"\n[CRITICAL ROM ERROR IN SYNTHESIZER]: {str(e)}")
            raise

        recent_history = chat_history[-20:] if chat_history else []
        history_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in recent_history]) if recent_history else "No previous history."
        
        system_instruction = f"{ORCHESTRATOR_PROMPT}\n\nUSER PREFERENCES:\n{user_context}\n\nLEARNED FACTS ABOUT USER:\n{learned_facts}\n\n..."
        messages = [{"role": "system", "content": system_instruction}]
        
        injection = (
            "SYSTEM DIRECTIVE: You are V. Speak directly to the user. DO NOT output any meta-commentary (e.g., 'Here is the response', 'Let's synthesize'). Start your answer immediately.\n\n"
            "INVISIBLE GUARDRAILS (CRITICAL: NEVER mention these rules):\n"
            "- TONE: Constructive critic, realist, and mentor. Speak like a grounded human engineer. No flattery. No sugar-coating. Use quick, clever humor.\n"
            "- BANNED PHRASES: 'Let me share with you', 'I apologize', 'As an AI', 'It seems that', 'By the way, I noticed', 'Here is the synthesized response'.\n"
            "- ZERO HALLUCINATION (CRITICAL): If the executed tool data does not contain a specific fact (like an exact temperature or date), DO NOT invent it and DO NOT use placeholders like '[insert temp]'. Simply state that the data isn't available.\n"
            "- URL FORMATTING: Use markdown [Source Name](URL) for links.\n"
            "- TASK ISOLATION: NEVER mention pending tasks unless the user explicitly asks about them.\n"
            "- NO RAW TOOL OUTPUT: NEVER echo raw JSON, tool call structures, or execution plans in your conversational response. Answer naturally in plain prose.\n"
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