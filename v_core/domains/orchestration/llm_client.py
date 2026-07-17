import json
import aiohttp
from typing import AsyncGenerator
from v_core.domains.tools.tool_registry import registry

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3"

async def planner_llm_call(prompt: str, previous_results: list) -> str:
    """
    Evaluates the prompt and current tool history using local Ollama.
    Enforces strict JSON formatting.
    """
    # Dynamically pull the schemas from your registry so the model knows what it can do
    tool_schemas = registry.get_all_schemas()
    
    system_instruction = (
        "You are V's routing cognitive core. Your job is to analyze the user prompt and previous tool results. "
        f"Available tools: {json.dumps(tool_schemas)}. "
        "You must respond ONLY in strict JSON format. Do not include markdown code blocks. "
        "Your JSON must contain a 'status' key (either 'need_data' or 'ready_to_synthesize') "
        "and a 'tool_calls' array containing objects with 'name' and 'args' keys."
    )
    
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"User Prompt: {prompt}\n\nPrevious Tool Results: {json.dumps(previous_results)}"}
    ]
    
    async with aiohttp.ClientSession() as session:
        async with session.post(OLLAMA_URL, json={
            "model": MODEL_NAME,
            "messages": messages,
            "format": "json", # Forces Ollama to lock into JSON generation
            "stream": False
        }) as response:
            if response.status != 200:
                raise Exception(f"Ollama API Error: {response.status}")
            
            result = await response.json()
            return result["message"]["content"]

async def synthesizer_stream(prompt: str, results: list) -> AsyncGenerator[str, None]:
    """
    Reads the successful tool results and streams the final response token-by-token from Ollama.
    """
    system_instruction = (
        "You are V, an advanced AI assistant. Synthesize the provided tool results into a "
        "natural, concise, and conversational response to the user's prompt. Do not narrate your process."
    )
    
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"User Prompt: {prompt}\n\nTool Results: {json.dumps(results)}"}
    ]

    async with aiohttp.ClientSession() as session:
        async with session.post(OLLAMA_URL, json={
            "model": MODEL_NAME,
            "messages": messages,
            "stream": True
        }) as response:
            if response.status != 200:
                yield "Error: Failed to connect to local Ollama instance."
                return
                
            async for line in response.content:
                if line:
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]