import json
import aiohttp
from typing import AsyncGenerator, List, Dict
from v_core.domains.tools.tool_registry import registry

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3"

async def planner_llm_call(prompt: str, previous_results: list, chat_history: List[Dict[str, str]]) -> str:
    tool_schemas = registry.get_all_schemas()
    
    messages = [{"role": "system", "content": "You are V's routing core. Your only purpose is to output valid JSON."}]
    
    for turn in chat_history:
        messages.append(turn)
        
    injection = (
        f"Available Tools: {json.dumps(tool_schemas)}\n\n"
        "CRITICAL ROUTING RULES:\n"
        "1. REAL-TIME / SEARCH QUERIES: If asked for fresh facts, news, documentation, or references, call 'search_api'.\n"
        "2. SPECIFIC URLS ONLY: ONLY call 'web_scraper' if the user provides an explicit URL (e.g. 'https://...').\n"
        "3. LOCAL DATA: Call 'directory_scanner' or 'file_reader' for local filesystem requests.\n"
        "4. NO UNNECESSARY CALLS: If the prompt is basic common sense, math, or conversation, return an empty array [].\n\n"
        "EXAMPLES:\n"
        "Prompt: 'Search for recent ESP32-S3 TWAI documentation'\n"
        "Output: {\"status\": \"need_data\", \"tool_calls\": [{\"name\": \"search_api\", \"args\": {\"query\": \"ESP32-S3 TWAI documentation\"}}]}\n\n"
        "Prompt: 'Read https://github.com/espressif/arduino-esp32'\n"
        "Output: {\"status\": \"need_data\", \"tool_calls\": [{\"name\": \"web_scraper\", \"args\": {\"url\": \"https://github.com/espressif/arduino-esp32\"}}]}\n\n"
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
    messages = [{"role": "system", "content": "You are V, a helpful advanced desktop agent."}]
    
    for turn in chat_history:
        messages.append(turn)
        
    injection = (
        "SYSTEM DIRECTIVE: Synthesize any tool results into a crisp, natural response.\n"
        "CITATION RULE: When tool data contains web search snippets from 'search_api', "
        "cite facts using inline links/brackets like [Title](URL).\n"
        "Do not mention JSON schemas or internal tool names.\n\n"
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