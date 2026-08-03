import json
import re
import aiohttp
import inspect
import os

from typing import Dict, Any
from agents.tools.tool_registry import registry
from agents.tools.preconditions import BaseTool, SecurityTier
from pydantic import ValidationError
from agents.orchestration.schemas import CognitivePlan

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
        
        all_schemas = registry.get_all_schemas()
        tool_schemas = [schema for schema in all_schemas if schema.get("name") in self.allowed_tools]

        system_instruction = (
            "You are V's Research Sub-Agent. Your only job is to execute research and return a factual brief.\n"
            f"Available Tools: {json.dumps(tool_schemas)}\n"
            "You MUST output ONLY valid JSON matching this exact schema:\n"
            "{\n"
            '  "tool_calls": [\n'
            '    {\n'
            '      "name": "tool_name_here",\n'
            '      "args": {"arg_name": "arg_value"}\n'
            '    }\n'
            '  ]\n'
            "}\n"
            "If you do not need a tool, return an empty tool_calls array."
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
                plan_payload = result["message"]["content"]
                
        # 3. STRICT VALIDATION: Coerce the string directly into our Pydantic model
        try:
            clean_payload = re.sub(r'```(?:json)?\n?(.*?)\n?```', r'\1', plan_payload, flags=re.DOTALL).strip()
            validated_plan = CognitivePlan.model_validate_json(clean_payload)
        except ValidationError as e:
            # Sub-agent gracefully returns the error instead of crashing the backend
            return f"Research Sub-Agent failed: Schema validation error - {str(e)}"
        except json.JSONDecodeError:
            return "Research Sub-Agent failed: LLM did not output valid JSON."
                
        # 4. Execute the delegated tool using type-safe Pydantic objects
        research_data = []
        if validated_plan.tool_calls:
            for tool in validated_plan.tool_calls:
                if tool.name in self.allowed_tools:
                    tool_instance = registry.get_tool(tool.name)
                    
                    if tool_instance is None:
                        continue
                        
                    # THE FIX: Sanitize args in case Ollama wrapped them in lists
                    sanitized_args = {}
                    for key, value in tool.args.items():
                        sanitized_args[key] = value[0] if isinstance(value, list) and len(value) == 1 else value
                        
                    if inspect.iscoroutinefunction(tool_instance.execute):
                        res = await tool_instance.execute(**sanitized_args)
                    else:
                        import asyncio
                        res = await asyncio.to_thread(tool_instance.execute, **sanitized_args)
                    
                    if res:
                        research_data.append(res)
                
        # THE FIX: Stop the hallucination at the source by refusing to return empty arrays
        if not research_data or research_data == [[]] or research_data == [{"error": "Search execution failed"}]:
            return "Research Sub-Agent failed: No web data found. CRITICAL: Inform the user the search failed. Do NOT invent or hallucinate URLs."
            
        # 5. Return the raw data to the main Synthesizer
        return f"Research Sub-Agent Brief: {json.dumps(research_data)}"

# Register the sub-agent into the system as a high-level tool
registry.register_tool("research_agent", ResearchSubAgent())