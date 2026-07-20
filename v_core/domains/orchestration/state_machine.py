import asyncio
import json
import re
import inspect

from v_core.domains.tools.tool_registry import registry
from v_core.domains.orchestration.llm_client import planner_llm_call, synthesizer_stream
from v_core.domains.memory.router import MemoryRouter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DB_PATH = BASE_DIR / "data" / "rom.db"

router = MemoryRouter(db_path=str(DB_PATH))

async def execute_tool_async(tool_name: str, args: dict) -> dict:
    """
    Secure bridge enforcing BaseTool preconditions and SecurityTiers.
    """
    if not registry.has_tool(tool_name):
         return {"status": "failed", "error": f"Tool '{tool_name}' not found in registry."}

    tool_instance = registry.get_tool(tool_name)

    # FIX: Explicit 'is None' check to satisfy Pylance's static type narrowing
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
    await yield_queue.put({"type": "status", "content": "Initializing cognitive routing..."})
    tool_results = []
    
    # --- STEP 0: CONTEXT ROUTING (New) ---
    retrieved_context = await asyncio.to_thread(router.evaluate_and_fetch, prompt)
    
    if retrieved_context:
        # Augment the prompt invisibly so the LLM gets the memory
        prompt = f"{prompt}\n\n[SYSTEM MEMORY INJECTION]: {retrieved_context}"
        await yield_queue.put({"type": "status", "content": "Context retrieved from ROM."})
    
    # --- STEP 1: PLAN ---
    await yield_queue.put({"type": "status", "content": "Planning execution path..."})
    plan_payload = await planner_llm_call(prompt, tool_results, chat_history) #[cite: 2, 3]
    
    try:
        # Shred unwanted markdown wrappers
        clean_payload = re.sub(r'```(?:json)?\n?(.*?)\n?```', r'\1', plan_payload, flags=re.DOTALL).strip()
        plan = json.loads(clean_payload)
    except json.JSONDecodeError:
        # If it hallucinates non-JSON, skip execution and synthesize the error immediately
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
    
    async for token in synthesizer_stream(prompt, tool_results, chat_history):
        await yield_queue.put({"type": "token", "content": token})
        
    await yield_queue.put({"type": "done", "content": ""})