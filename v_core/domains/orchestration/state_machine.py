import asyncio
import json
from typing import AsyncGenerator, Dict, Any

# Mock imports based on your KeepSafe architecture
# from v_core.domains.memory.ram_window import update_ram_window
# from v_core.domains.tools.tool_registry import execute_tool_async

async def run_cognitive_graph(prompt: str, yield_queue: asyncio.Queue, max_iterations: int = 3):
    """
    Executes the Supervisor-led cognitive loop.
    Prevents compounding errors by validating tool execution before synthesis.
    """
    await yield_queue.put({"type": "status", "content": "Initializing cognitive routing..."})
    
    # Context Compaction Check could happen here before we start
    # ram_status = await check_ram_window() 
    
    current_iteration = 0
    tool_results = []
    task_complete = False

    while current_iteration < max_iterations and not task_complete:
        current_iteration += 1
        await yield_queue.put({"type": "status", "content": f"Planning cycle {current_iteration}..."})
        
        # 1. ORCHESTRATOR / PLANNER 
        # In production, this call must enforce Strict JSON mode.
        plan_payload = await mock_planner_llm_call(prompt, tool_results)
        
        try:
            plan = json.loads(plan_payload)
        except json.JSONDecodeError:
            await yield_queue.put({"type": "error", "content": "Failed to parse Planner output. Retrying..."})
            continue # Loop back and let the LLM correct itself

        # If the Planner decides it has enough info, break to Synthesizer
        if plan.get("status") == "ready_to_synthesize":
            task_complete = True
            break

        # 2. EXECUTOR (Async & Isolated)
        if plan.get("tool_calls"):
            for tool in plan["tool_calls"]:
                tool_name = tool.get('name')
                
                # Check Sandboxing / Preconditions here
                await yield_queue.put({"type": "status", "content": f"Executing {tool_name}..."})
                
                try:
                    # execute_tool_async would handle the actual invocation
                    result = await mock_execute_tool_async(tool_name, tool.get('args'))
                    tool_results.append({"tool": tool_name, "status": "success", "data": result})
                    
                except Exception as e:
                    # Catch brittle connector failures (e.g., API timeouts)
                    error_msg = f"Tool {tool_name} failed: {str(e)}"
                    tool_results.append({"tool": tool_name, "status": "failed", "error": error_msg})
                    await yield_queue.put({"type": "warning", "content": error_msg})
                    # The loop will restart, giving the Planner a chance to observe the failure

    # 3. SYNTHESIZER
    if not task_complete:
        await yield_queue.put({"type": "warning", "content": "Max iterations reached. Forcing synthesis."})

    await yield_queue.put({"type": "status", "content": "Synthesizing final response..."})
    
    # Stream the final natural language response
    async for token in mock_synthesizer_stream(prompt, tool_results):
        await yield_queue.put({"type": "token", "content": token})
        
    await yield_queue.put({"type": "done", "content": ""})

# --- Mock Functions for structural testing ---
async def mock_planner_llm_call(prompt: str, previous_results: list) -> str:
    await asyncio.sleep(0.5)
    if not previous_results:
        return json.dumps({"status": "need_data", "tool_calls": [{"name": "directory_scanner", "args": {"path": "./"}}]})
    return json.dumps({"status": "ready_to_synthesize"})

async def mock_execute_tool_async(name: str, args: dict) -> str:
    await asyncio.sleep(1)
    return f"Executed {name} successfully."

async def mock_synthesizer_stream(prompt: str, results: list) -> AsyncGenerator[str, None]:
    words = ["Here", " is", " the", " synthesized", " data", " based", " on", " the", " tools."]
    for word in words:
        await asyncio.sleep(0.1)
        yield word