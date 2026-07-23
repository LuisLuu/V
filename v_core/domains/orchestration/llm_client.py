import json
import aiohttp
from typing import AsyncGenerator, List, Dict
from v_core.domains.tools.tool_registry import registry

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3"

async def planner_llm_call(prompt: str, previous_results: list, chat_history: List[Dict[str, str]]) -> str:
    tool_schemas = registry.get_all_schemas()
    
    # Flatten history into text to avoid strict Ollama role-alternating errors (400 Bad Request)
    history_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history]) if chat_history else "No previous history."
    
    system_instruction = (
        "You are V's routing core. Your only purpose is to output valid JSON containing tool execution plans.\n"
        f"RECENT CONVERSATION HISTORY:\n{history_text}\n"
    )
    
    messages = [{"role": "system", "content": system_instruction}]
    
    injection = (
        f"Available Tools: {json.dumps(tool_schemas)}\n\n"
        "CRITICAL ROUTING RULES:\n"
        "1. REAL-TIME / WEATHER / SEARCH: If asked for weather, news, facts, or references, call 'search_api' or 'rest_caller'.\n"
        "2. SPECIFIC URLS ONLY: ONLY call 'web_scraper' if the user provides an explicit URL (e.g., 'https://...').\n"
        "3. TASKS & REMINDERS: If the user asks to add, complete, remove, or view tasks/reminders, YOU MUST call the 'task_manager' tool.\n"
        "4. NO UNNECESSARY CALLS: If the prompt is basic conversation or math, return an empty array [].\n\n"
    )
    
    user_content = f"{injection}CURRENT TURN PROMPT: {prompt}"
    if previous_results:
        user_content += f"\nCURRENT TURN TOOL DATA: {json.dumps(previous_results)}"
        
    messages.append({"role": "user", "content": user_content})
    
    async with aiohttp.ClientSession() as session:
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

async def synthesizer_stream(prompt: str, results: list, chat_history: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
    # Flatten history here as well
    history_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history]) if chat_history else "No previous history."
    
    system_instruction = (
        "You are V, a helpful advanced desktop agent.\n"
        f"RECENT CONVERSATION HISTORY:\n{history_text}\n"
    )
    
    messages = [{"role": "system", "content": system_instruction}]
    
    injection = (
        "SYSTEM DIRECTIVE: Synthesize any tool results into a crisp, natural response.\n"
        "ANTI-HALLUCINATION RULE: NEVER claim to have completed an action (like adding, updating, or deleting a task) UNLESS the 'Executed Tool Data' explicitly confirms a 'success' status. If the tool data is empty or shows an error, you must tell the user the action failed.\n"
        "CITATION RULE: When tool data contains web search snippets, cite facts using inline links/brackets like [Title](URL).\n"
        "Do not mention JSON schemas or internal tool names to the user.\n\n"
    )
    
    user_content = f"{injection}User Prompt: {prompt}"
    if results:
        user_content += f"\nExecuted Tool Data: {json.dumps(results)}"
        
    messages.append({"role": "user", "content": user_content})

    async with aiohttp.ClientSession() as session:
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