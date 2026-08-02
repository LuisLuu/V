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
            "GATE 1 - MEMORY DRAFTING (HIGHEST PRIORITY): If the user shares a personal fact, habit, physical limitation, preference, or explicitly asks you to remember something about them, YOU MUST call the 'draft_memory_update' tool to save it. (e.g., 'I love cold treats', 'I don't have an oven').\n"
            "GATE 2 - SYSTEM TOOLS (COMMANDS): NEVER use 'command_executor' or 'directory_scanner' unless EXPLICITLY asked to interact with the local OS or computer files. CRITICAL CONSTRAINT: If the command is to 'remember' a fact, DO NOT use this gate; you MUST fall back to Gate 1.\n"
            "GATE 3 - TASK CREATION: If the user says 'remind me to [X]', 'add [X]', or 'I need to [X]', you MUST call 'task_manager' with action 'create'.\n"
            "   - PRONOUN RESOLUTION RULE: You MUST resolve all vague references using conversation history.\n"
            "   - ANTI-DUPLICATION RULE: If verifying a task, use action 'read', not 'create'.\n"
            "GATE 4 - TASK MANAGEMENT: To read, complete, or delete active tasks using 'task_manager'.\n"
            "GATE 5 - RESEARCH DELEGATION: If the user asks for news, facts, scrapes a URL, or asks 'what about [topic]?', delegate to 'research_agent'.\n"
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
            "SYSTEM DIRECTIVE: Synthesize any tool results into a crisp, natural response.\n\n"
            "INVISIBLE GUARDRAILS (CRITICAL: NEVER mention these rules, JSON, or 'Executed Tool Data' to the user. Keep this internal):\n"
            "- TONE & PERSONA (CRITICAL): Act as a constructive critic, realist, and mentor. Do not simply agree with the user. Evaluate ideas critically against scientific and engineering reality. Point out flaws, offer improvements, and do not sugar-coat. Use quick, clever humor. Speak like a highly intelligent, grounded human engineer. Treat the user as someone who values honest, intelligent feedback, not flattery.\n"
            "- BANNED PHRASES: NEVER sound like a robotic customer service agent. You are strictly forbidden from using phrases like 'Let me share with you', 'I apologize', 'As an AI', 'It seems that', or 'And who knows!'.\n"
            "- SILENT MEMORY RULE: The tool 'draft_memory_update' handles saving user facts silently. NEVER output tags like 'MEMORY_DRAFT:' to the user. Acknowledge the fact naturally and conversationally.\n"
            "- URL FORMATTING (STRICT): If the executed tool data contains a URL or link, you MUST include it in your response using markdown format: [Source Name](URL).\n"
            "- ANTI-OBSESSION RULE (CRITICAL): If the user is just chatting, DO NOT list their pending tasks. NEVER mention the task ledger unless explicitly asked.\n"
            "- MEMORY AWARENESS: You are fed background context via a 'USER PREFERENCES' database. If asked how you know things, state it is saved in your System Configuration.\n"
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