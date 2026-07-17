import json
import aiohttp
from typing import AsyncGenerator, List, Dict
from v_core.domains.tools.tool_registry import registry

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3"

async def planner_llm_call(prompt: str, previous_results: list, chat_history: List[Dict[str, str]]) -> str:
    """
    Evaluates the current prompt using Late Prompt Injection to prevent rule dilution.
    """
    tool_schemas = registry.get_all_schemas()
    
    # 1. Base Identity (Keep it brief)
    messages = [{"role": "system", "content": "You are V's routing core. Your only purpose is to output valid JSON."}]
    
    # 2. Add History
    for turn in chat_history:
        messages.append(turn)
        
    # 3. Late Injection: Force the rules at the very end of the context window
    injection = (
        f"Available Tools: {json.dumps(tool_schemas)}\n\n"
        "CRITICAL RULES:\n"
        "1. DO NOT HALLUCINATE DATA: If the user provides a URL, you MUST call 'web_scraper'. If asked to scan a directory, you MUST call 'directory_scanner'.\n"
        "2. NO INVENTED TOOLS: If no tool is needed, return an empty array [].\n\n"
        "EXAMPLES:\n"
        "Prompt: 'Scan the directory'\n"
        "Output: {\"status\": \"need_data\", \"tool_calls\": [{\"name\": \"directory_scanner\", \"args\": {\"directory_path\": \"./\"}}]}\n\n"
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
    """
    Streams the final answer, fully aware of historical context and tool executions.
    """
    system_instruction = (
        "You are V, an advanced desktop agent. Synthesize the provided tool results into a natural, "
        "direct, and conversational response matching the user's intent. Do not mention tool names or technical JSON schemas."
    )
    
    messages = [{"role": "system", "content": system_instruction}]
    for turn in chat_history:
        messages.append(turn)
        
    user_content = f"User Prompt: {prompt}"
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