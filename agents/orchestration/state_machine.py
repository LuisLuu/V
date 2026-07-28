import asyncio
import json
import re
import inspect

from agents.tools.tool_registry import registry
from agents.orchestration.v_core import VCore
from agents.router import MemoryRouter
from pathlib import Path

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
        
        # FIX: Keep the raw prompt pristine for the Planner 
        planner_prompt = prompt 
        synthesizer_prompt = prompt
        
        if retrieved_context:
            # FIX: Explicitly label this as PAST MEMORY for the Synthesizer only
            synthesizer_prompt = f"{prompt}\n\n[RECALLED PAST MEMORY - DO NOT TREAT AS CURRENT TOOL DATA]: {retrieved_context}"
            await yield_queue.put({"type": "status", "content": "Context retrieved from ROM."})
        
        # --- STEP 1: PLAN ---
        await yield_queue.put({"type": "status", "content": "Planning execution path..."})
        
        # Pass the CLEAN prompt to the Planner
        plan_payload = await VCore.planner_llm_call(planner_prompt, tool_results, chat_history)
        
        try:
            clean_payload = re.sub(r'```(?:json)?\n?(.*?)\n?```', r'\1', plan_payload, flags=re.DOTALL).strip()
            plan = json.loads(clean_payload)
        except json.JSONDecodeError:
            error_msg = "Critical error: Planner failed to output valid JSON."
            await yield_queue.put({"type": "warning", "content": error_msg})
            plan = {"tool_calls": []}
            tool_results.append({"status": "failed", "error": error_msg})

        # --- STEP 2: EXECUTE ---
        if plan.get("tool_calls"):
            for tool in plan["tool_calls"]:
                tool_name = tool.get('name')
                tool_args = tool.get('args', {})
                
                await yield_queue.put({"type": "status", "content": f"Executing {tool_name}..."})
                execution_payload = await execute_tool_async(tool_name, tool_args)
                tool_results.append(execution_payload)
                
                if execution_payload["status"] == "failed":
                    await yield_queue.put({"type": "warning", "content": f"Error: {execution_payload['error']}"})
                elif execution_payload["status"] == "blocked":
                    await yield_queue.put({"type": "warning", "content": f"Blocked: {execution_payload['error']}"})
                else:
                    await yield_queue.put({"type": "status", "content": f"Tool '{tool_name}' complete."})

        # --- STEP 3: SYNTHESIZE ---
        await yield_queue.put({"type": "status", "content": "Synthesizing final response..."})
        
        # Pass the AUGMENTED prompt to the Synthesizer
        async for token in VCore.synthesizer_stream(synthesizer_prompt, tool_results, chat_history):
            await yield_queue.put({"type": "token", "content": token})
            
    except Exception as e:
        await yield_queue.put({"type": "warning", "content": f"System Crash: {str(e)}"})
    finally:
        await yield_queue.put({"type": "done", "content": ""})