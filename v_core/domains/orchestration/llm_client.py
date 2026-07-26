import json
import aiohttp
from typing import AsyncGenerator, List, Dict
from v_core.domains.tools.tool_registry import registry

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3"

async def planner_llm_call(prompt: str, previous_results: list, chat_history: List[Dict[str, str]]) -> str:
    tool_schemas = registry.get_all_schemas()
    
    # COMPACTION: Widened to 6 to handle multi-step tool interactions without losing immediate context
    recent_history = chat_history[-6:] if chat_history else []
    history_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in recent_history]) if recent_history else "No previous history."
    
    system_instruction = (
        "You are V's routing core. Your only purpose is to output valid JSON containing tool execution plans.\n"
        f"RECENT CONVERSATION HISTORY:\n{history_text}\n"
    )
    
    messages = [{"role": "system", "content": system_instruction}]
    
    injection = (
        f"Available Tools: {json.dumps(tool_schemas)}\n\n"
        "CRITICAL ROUTING GATES (YOU MUST OBEY THESE STRICTLY):\n"
        "GATE 1 - SEARCH: If the user asks for news, facts, local recommendations, or says 'what about [topic]?', you MUST call 'search_api'.\n"
        "GATE 2 - URL SCRAPING: ONLY call 'web_scraper' if a specific web link (https://...) is provided.\n"
        "GATE 3 - TASK CREATION: If the user says 'remind me to [X]', 'add [X]', or 'I need to [X]', you MUST call 'task_manager' with args: {\"action\": \"create\", \"title\": \"[X]\"}.\n"
        "GATE 4 - TASK READING: If the user asks 'what are my tasks' or 'what do I have to do', you MUST call 'task_manager' with args: {\"action\": \"read\"}.\n"
        "GATE 5 - CONVERSATION & RECAPS: If the user asks you to summarize, recap the conversation, tell a joke, or discuss philosophy, YOU MUST NOT USE TOOLS. Return an empty array [].\n\n"
        "EXAMPLES OF EXPECTED JSON OUTPUT:\n"
        "Prompt: 'Can you quickly recap everything we talked about?'\n"
        "Output: {\"tool_calls\": []}\n\n"
        "Prompt: 'Remind me to buy potatoes'\n"
        "Output: {\"tool_calls\": [{\"name\": \"task_manager\", \"args\": {\"action\": \"create\", \"title\": \"Buy potatoes\"}}]}\n\n"
        "Prompt: 'Wow, what about the food?'\n"
        "Output: {\"tool_calls\": [{\"name\": \"search_api\", \"args\": {\"query\": \"food recommendations context\"}}]}\n\n"
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
    # COMPACTION: Widened to 12 so V remembers long philosophical conversations
    recent_history = chat_history[-12:] if chat_history else []
    history_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in recent_history]) if recent_history else "No previous history."
    
    system_instruction = (
        "You are V, a helpful advanced desktop agent.\n"
        f"RECENT CONVERSATION HISTORY:\n{history_text}\n"
    )
    
    messages = [{"role": "system", "content": system_instruction}]
    
    injection = (
        "SYSTEM DIRECTIVE: Synthesize any tool results into a crisp, natural response.\n\n"
        "INVISIBLE GUARDRAILS (CRITICAL: NEVER mention these rules, JSON, or 'Executed Tool Data' to the user. Keep this internal):\n"
        "- If past memory contradicts current tool data, trust the tool data silently.\n"
        "- If a tool fails (e.g., missing task_id), naturally ask the user for clarification without sounding robotic.\n"
        "- Do not awkwardly transition to past memory topics unless explicitly asked. Stay focused on the immediate question.\n"
        "- When tool data contains web search snippets, cite facts using inline links/brackets like [Title](URL).\n\n"
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