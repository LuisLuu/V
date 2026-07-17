import json
import aiohttp
from typing import AsyncGenerator, List, Dict
from v_core.domains.tools.tool_registry import registry

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3"

async def planner_llm_call(prompt: str, previous_results: list, chat_history: List[Dict[str, str]]) -> str:
    """
    Evaluates the current prompt and forces strict tool usage using Few-Shot examples.
    """
    tool_schemas = registry.get_all_schemas()
    
    system_instruction = (
        "You are V, a powerful desktop routing core. You have FULL authorization to access local files and the internet.\n"
        f"Available Tools: {json.dumps(tool_schemas)}\n\n"
        "CRITICAL RULES:\n"
        "1. DO NOT FAKE DATA: Never output placeholder text like '[list of files]'. If you need data, call the tool.\n"
        "2. URLs = SCRAPER: If the user provides a URL, you MUST call 'web_scraper'.\n"
        "3. NO INVENTED TOOLS: Never output a tool named 'None'. If no tool is needed, use an empty list [].\n\n"
        "EXAMPLES OF CORRECT JSON OUTPUT:\n"
        "User: 'Scan the current directory'\n"
        "Output: {\"status\": \"need_data\", \"tool_calls\": [{\"name\": \"directory_scanner\", \"args\": {\"directory_path\": \"./\"}}]}\n\n"
        "User: 'What is on https://www.example.com?'\n"
        "Output: {\"status\": \"need_data\", \"tool_calls\": [{\"name\": \"web_scraper\", \"args\": {\"url\": \"https://www.example.com\"}}]}\n\n"
        "User: 'Hi' OR 'Tell me a joke' OR 'What did I just ask you?'\n"
        "Output: {\"status\": \"ready_to_synthesize\", \"tool_calls\": []}\n"
    )
    
    messages = [{"role": "system", "content": system_instruction}]
    
    for turn in chat_history:
        messages.append(turn)
        
    user_content = f"CURRENT TURN PROMPT: {prompt}"
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
    if results: # FIX: Using the correct parameter name here
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