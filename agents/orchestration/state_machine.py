import asyncio
import json
import re
import inspect
import agents.orchestration.sub_agents

from pathlib import Path
from agents.tools.tool_registry import registry
from agents.orchestration.v_core import VCore
from agents.router import MemoryRouter
from pydantic import ValidationError
from agents.orchestration.schemas import CognitivePlan

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DB_PATH = BASE_DIR / "memory" / "rom.db"

router = MemoryRouter(db_path=str(DB_PATH))

async def execute_tool_async(tool_name: str, args: dict) -> dict:
    """
    Secure bridge enforcing BaseTool preconditions and SecurityTiers.
    """
    if not registry.has_tool(tool_name):
         return {"status": "failed", "error": f"Tool '{tool_name}' not found in registry."}

    tool_instance = registry.get_tool(tool_name)

    if tool_instance is None:
        return {"status": "failed", "error": f"Tool '{tool_name}' failed to load."}

    # 1. Hardware/Environment Precondition Check
    if not tool_instance.verify_preconditions():
        return {"tool": tool_name, "status": "failed", "error": "Causal sensors rejected execution."}

    # 2. Security Tier Check (Human-in-the-Loop)
    if tool_instance.security_tier.value == "human_approval":
        return {"tool": tool_name, "status": "blocked", "error": "DESTRUCTIVE action requires approval."}

    try:
        # 3. Execution Sandbox
        if inspect.iscoroutinefunction(tool_instance.execute):
            result = await tool_instance.execute(**args)
        else:
            result = await asyncio.to_thread(tool_instance.execute, **args)
        return {"tool": tool_name, "status": "success", "data": result}
    except Exception as e:
        return {"tool": tool_name, "status": "failed", "error": str(e)}

async def run_cognitive_graph(prompt: str, yield_queue: asyncio.Queue, chat_history: list):
    """
    Executes a strict, loop-free 0-1-2-3 cognitive pipeline.
    """
    try:
        await yield_queue.put({"type": "status", "content": "Initializing cognitive routing..."})
        tool_results = []
        
        # --- STEP 0: CONTEXT ROUTING ---
        retrieved_context = await asyncio.to_thread(router.evaluate_and_fetch, prompt)
        
        planner_prompt = prompt
        synthesizer_prompt = prompt
        
        if retrieved_context:
            # FIX: Feed the memory to the Planner so it can make intelligent tool decisions
            memory_injection = f"\n\n[RECALLED PAST MEMORY]: {retrieved_context}"
            planner_prompt += memory_injection
            synthesizer_prompt += memory_injection
            await yield_queue.put({"type": "status", "content": "Context retrieved from ROM."})
        
        # --- STEP 1: PLAN ---
        await yield_queue.put({"type": "status", "content": "Planning execution path..."})
        
        plan_payload = await VCore.planner_llm_call(planner_prompt, tool_results, chat_history)
        
        try:
    # 1. Clean the payload (keep your regex just in case the LLM wraps it in markdown)
            clean_payload = re.sub(r'```(?:json)?\n?(.*?)\n?```', r'\1', plan_payload, flags=re.DOTALL).strip()
            
            # 2. STRICT VALIDATION: Coerce the string directly into our Pydantic model
            validated_plan = CognitivePlan.model_validate_json(clean_payload)

        except ValidationError as e:
            # Pydantic caught a structural error (e.g., missing 'tool_calls' list)
            error_msg = f"Critical error: Planner output failed schema validation. Details: {str(e)}"
            await yield_queue.put({"type": "warning", "content": error_msg})
            validated_plan = CognitivePlan(tool_calls=[])
            tool_results.append({"status": "failed", "error": error_msg})
        except json.JSONDecodeError:
            # The LLM output wasn't even JSON
            error_msg = "Critical error: Planner failed to output valid JSON."
            await yield_queue.put({"type": "warning", "content": error_msg})
            validated_plan = CognitivePlan(tool_calls=[])
            tool_results.append({"status": "failed", "error": error_msg})

        if validated_plan.tool_calls:
            
            # --- THE CIRCUIT BREAKER ---
            # Prevent the LLM from panic-spamming tools
            MAX_TOOLS = 3
            if len(validated_plan.tool_calls) > MAX_TOOLS:
                await yield_queue.put({
                    "type": "warning", 
                    "content": f"System Overload: Planner requested {len(validated_plan.tool_calls)} tools. Truncating to {MAX_TOOLS}."
                })
                validated_plan.tool_calls = validated_plan.tool_calls[:MAX_TOOLS]
                
            for tool in validated_plan.tool_calls:

                sanitized_args = {}
                for key, value in tool.args.items():
                    if isinstance(value, list) and len(value) == 1:
                        sanitized_args[key] = value[0] # Extract the single item
                    else:
                        sanitized_args[key] = value
                                
                await yield_queue.put({"type": "status", "content": f"Executing {tool.name}..."})
                execution_payload = await execute_tool_async(tool.name, sanitized_args)
                tool_results.append(execution_payload)
                
                if execution_payload["status"] == "failed":
                    await yield_queue.put({"type": "warning", "content": f"Error: {execution_payload['error']}"})
                elif execution_payload["status"] == "blocked":
                    await yield_queue.put({"type": "warning", "content": f"Blocked: {execution_payload['error']}"})
                else:
                    await yield_queue.put({"type": "status", "content": f"Tool '{tool.name}' complete."})

        # --- STEP 3: SYNTHESIZE ---
        await yield_queue.put({"type": "status", "content": "Synthesizing final response..."})
        
        async for token in VCore.synthesizer_stream(synthesizer_prompt, tool_results, chat_history):
            await yield_queue.put({"type": "token", "content": token})
            
    except Exception as e:
        await yield_queue.put({"type": "warning", "content": f"System Crash: {str(e)}"})
    finally:
        await yield_queue.put({"type": "done", "content": ""})