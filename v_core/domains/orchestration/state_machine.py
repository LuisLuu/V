import asyncio
import json
import inspect

from v_core.domains.tools.tool_registry import registry
from v_core.domains.orchestration.llm_client import planner_llm_call, synthesizer_stream

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

async def run_cognitive_graph(prompt: str, yield_queue: asyncio.Queue, chat_history: list, max_iterations: int = 3):
    """
    Executes the Supervisor-led cognitive loop with short-term memory tracking.
    """
    await yield_queue.put({"type": "status", "content": "Initializing cognitive routing..."})
    
    current_iteration = 0
    tool_results = []
    task_complete = False

    while current_iteration < max_iterations and not task_complete:
        current_iteration += 1
        await yield_queue.put({"type": "status", "content": f"Planning cycle {current_iteration}..."})
        
        # Pass chat_history to the planner
        plan_payload = await planner_llm_call(prompt, tool_results, chat_history)
        
        try:
            plan = json.loads(plan_payload)
        except json.JSONDecodeError:
            await yield_queue.put({"type": "error", "content": "Failed to parse Planner output. Retrying..."})
            continue

        if plan.get("status") == "ready_to_synthesize":
            task_complete = True
            break

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

    if not task_complete:
        await yield_queue.put({"type": "warning", "content": "Max iterations reached. Forcing synthesis."})

    await yield_queue.put({"type": "status", "content": "Synthesizing final response..."})
    
    # Pass chat_history to the synthesizer stream
    async for token in synthesizer_stream(prompt, tool_results, chat_history):
        await yield_queue.put({"type": "token", "content": token})
        
    await yield_queue.put({"type": "done", "content": ""})