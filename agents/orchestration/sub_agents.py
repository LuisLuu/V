import json
import aiohttp
import inspect
from typing import Dict, Any
from agents.tools.tool_registry import registry
from agents.tools.preconditions import BaseTool, SecurityTier # Adjust import path if needed

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3"

# Inherit from BaseTool
class ResearchSubAgent(BaseTool):
    """
    A specialized sub-agent for factual grounding and web scraping.
    It acts as an independent microservice with a bounded context.
    """
    
    # Satisfy the BaseTool requirements
    security_tier = SecurityTier.READ
    preconditions = []
    
    def __init__(self):
        self.name = "research_agent"
        self.description = "Delegates deep research tasks. Call this agent when you need to search the web, check news, or scrape a URL."
        self.allowed_tools = ["search_api", "web_scraper"]

    def get_schema(self) -> Dict[str, Any]:
        """Registers the sub-agent as a 'tool' to the main Orchestrator."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "task_objective": {
                        "type": "string",
                        "description": "Detailed instructions on what needs to be researched."
                    }
                },
                "required": ["task_objective"]
            }
        }

    async def execute(self, task_objective: str) -> str:
        """The isolated cognitive loop for the Research Agent."""
        print(f"🕵️‍♂️ [SUB-AGENT] Research Agent activated for: {task_objective}")
        
        # FIX 1: Fetch all schemas and filter them, avoiding direct method calls on the Tool class
        all_schemas = registry.get_all_schemas()
        tool_schemas = [schema for schema in all_schemas if schema.get("name") in self.allowed_tools]

        system_instruction = (
            "You are V's Research Sub-Agent. Your only job is to execute research and return a factual brief.\n"
            f"Available Tools: {json.dumps(tool_schemas)}\n"
            "Output ONLY valid JSON to call a tool, or return a synthesized text brief if you have the answer."
        )
        
        # 2. Ask the Sub-Agent LLM how to accomplish the research
        async with aiohttp.ClientSession() as session:
            async with session.post(OLLAMA_URL, json={
                "model": MODEL_NAME,
                "messages": [{"role": "system", "content": system_instruction}, 
                             {"role": "user", "content": task_objective}],
                "format": "json",
                "stream": False
            }) as response:
                result = await response.json()
                plan = json.loads(result["message"]["content"])
                
        # 3. Execute the delegated tool
        research_data = []
        for tool in plan.get("tool_calls", []):
            tool_name = tool.get("name")
            tool_args = tool.get("args", {})
            
            if tool_name in self.allowed_tools:
                tool_instance = registry.get_tool(tool_name)
                
                # FIX 2: Type checker safety guard to ensure tool_instance isn't None
                if tool_instance is None:
                    continue
                    
                if inspect.iscoroutinefunction(tool_instance.execute):
                    res = await tool_instance.execute(**tool_args)
                else:
                    import asyncio
                    res = await asyncio.to_thread(tool_instance.execute, **tool_args)
                research_data.append(res)
                
        # 4. Return the raw data to the main Synthesizer
        return f"Research Sub-Agent Brief: {json.dumps(research_data)}"

# Register the sub-agent into the system as a high-level tool
registry.register_tool("research_agent", ResearchSubAgent())