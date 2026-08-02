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
from agents.tools.system.task_agent import TaskAgent
from agents.orchestration.auth_registry import auth_registry

# --- NEW: Import and instantiate the Blast Gate ---
from agents.harness.blast_gates import BlastGate
security_gate = BlastGate()

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DB_PATH = BASE_DIR / "memory" / "rom.db"

router = MemoryRouter(db_path=str(DB_PATH))

HIGH_RISK_TOOLS = {"command_executor", "terminal_run"} # Triggers Blast Gate
SAFE_TOOLS = {"task_manager", "memory_router", "conversational_bypass"} # Auto-approved

def sanitize_history(history: list) -> list:
    """Non-destructively strips raw tool JSON from the Planner's view of history."""
    clean = []
    for msg in history:
        if msg.get('role') not in ['user', 'assistant']:
            continue
        # Strip out the markdown JSON blocks to prevent the LLM from mimicking past tool calls
        clean_content = re.sub(r'```(?:json)?\n?.*?\n?```', '[Tool Execution Resolved]', msg.get('content', ''), flags=re.DOTALL).strip()
        if clean_content:
            clean.append({"role": msg['role'], "content": clean_content})
    return clean

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

    # ---> THE FIX: Bypass Blast Gate for Safe Tools <---
    if tool_name not in SAFE_TOOLS:
        # 2. Security Tier Check via BlastGate
        gate_evaluation = security_gate.evaluate_execution(tool_name, tool_instance.security_tier, args)
        
        if not gate_evaluation["approved"]:
            return {
                "tool": tool_name, 
                "status": gate_evaluation["status"], 
                "error": gate_evaluation.get("ui_prompt") or gate_evaluation.get("reason")
            }

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
        retrieved_context = None
        # Heuristic Bypass: Only run the heavy DB search if prompt has semantic weight
        if len(prompt.split()) > 3 and len(prompt) > 15:
            retrieved_context = await asyncio.to_thread(router.evaluate_and_fetch, prompt)
        
        planner_prompt = prompt
        synthesizer_prompt = prompt
        
        # RESTORED: Inject memory into both prompts if the router found something
        if retrieved_context:
            memory_injection = f"\n\n[RECALLED PAST MEMORY]: {retrieved_context}"
            planner_prompt += memory_injection
            synthesizer_prompt += memory_injection
            await yield_queue.put({"type": "status", "content": "Context retrieved from ROM."})
            
        await yield_queue.put({"type": "status", "content": "Syncing Task Ledger..."})
        try:
            task_agent = TaskAgent()
            all_tasks = await asyncio.to_thread(task_agent.list_tasks) 
            
            # CRITICAL FIX: Filter out completed tasks so V only sees what needs to be done
            active_tasks = [t for t in all_tasks if t['status'] in ['pending', 'in_progress']]
            
            task_list_str = ""
            if active_tasks:
                task_list_str = "\n".join([f"- [ID: {t['id']}] {t['title']} (Status: {t['status']})" for t in active_tasks])
            else:
                task_list_str = "No active tasks."
                
            state_injection = f"\n\n[CURRENT SYSTEM TASKS]:\n{task_list_str}"
            state_injection += "\n[CRITICAL RULE]: When asked to update or delete a task without an explicit ID, you must use the chat history to deduce which task the user means, find its ID in the list above, and INCLUDE the integer in your tool call."
            
            planner_prompt += state_injection
            synthesizer_prompt += state_injection
        except Exception as e:
            await yield_queue.put({"type": "warning", "content": f"Ledger Sync Failed: {e}"})
        # --------------------------------------------------------

        # --- STEP 1: PLAN ---
        await yield_queue.put({"type": "status", "content": "Planning execution path..."})
        
        clean_history = sanitize_history(chat_history)
        plan_payload = await VCore.planner_llm_call(planner_prompt, tool_results, clean_history)
        
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
            MAX_TOOLS = 3
            if len(validated_plan.tool_calls) > MAX_TOOLS:
                warning_msg = f"System Overload: Planner requested {len(validated_plan.tool_calls)} tools. Truncating to {MAX_TOOLS}."
                await yield_queue.put({"type": "warning", "content": warning_msg})
                
                # THE FIX: Tell the Synthesizer about the failure!
                tool_results.append({"status": "system_warning", "message": warning_msg, "dropped_tasks": len(validated_plan.tool_calls) - MAX_TOOLS})
                
                validated_plan.tool_calls = validated_plan.tool_calls[:MAX_TOOLS]
                
            for tool in validated_plan.tool_calls:
                sanitized_args = {}
                for key, value in tool.args.items():
                    if isinstance(value, list) and len(value) == 1:
                        sanitized_args[key] = value[0] 
                    else:
                        sanitized_args[key] = value
                                
                await yield_queue.put({"type": "status", "content": f"Evaluating {tool.name} safety..."})
                
                # 1. Fetch the tool instance to read its tier
                tool_instance = registry.get_tool(tool.name)
                if not tool_instance:
                    tool_results.append({"tool": tool.name, "status": "failed", "error": "Tool not found."})
                    continue

                # 2. ASK THE BLAST GATE FIRST
                gate_evaluation = security_gate.evaluate_execution(tool.name, tool_instance.security_tier, sanitized_args)
                
                # 3. Handle Human-In-The-Loop (HITL) dynamically based on the gate's decision
                if gate_evaluation["status"] == "HITL_REQUIRED":
                    # Convert args to a string so you can read them in the UI modal
                    command_str = str(sanitized_args) 
                    action_id = auth_registry.create_action(command_str)
                    
                    # Trigger the UI Modal
                    await yield_queue.put({
                        "type": "auth_request",
                        "action_id": action_id,
                        "command": command_str
                    })
                    
                    # PAUSE THE ENGINE
                    approved = await auth_registry.wait_for_approval(action_id)
                    
                    if not approved:
                        await yield_queue.put({"type": "warning", "content": f"Execution of '{tool.name}' denied."})
                        tool_results.append({"tool": tool.name, "status": "blocked", "error": "User denied authorization."})
                        continue # Skip execution and move to the next tool

                elif not gate_evaluation["approved"]:
                    # The gate hard-blocked it without asking for permission (e.g., unrecognized tier)
                    tool_results.append({"tool": tool.name, "status": "blocked", "error": gate_evaluation.get("reason", "Unknown block")})
                    continue
                
                # 4. If approved (either auto or manually), execute it
                # Make sure to remove the BlastGate code from inside execute_tool_async!
                execution_payload = await execute_tool_async(tool.name, sanitized_args)
                tool_results.append(execution_payload)
                
                # 2. INTERCEPTORS (Catch successful tools and push to frontend)
                if tool.name == "task_manager" and execution_payload["status"] == "success":
                    await yield_queue.put({"type": "task_update"})
                
                if tool.name == "draft_memory_update" and execution_payload["status"] == "success":
                    # Pushes the drafted memory text directly to the frontend queue
                    await yield_queue.put({"type": "memory_draft", "content": execution_payload.get("data", "")})
                                
                # 3. STATUS HANDLING (Process failures, blocks, and UI updates)
                if execution_payload["status"] == "failed":
                    await yield_queue.put({"type": "warning", "content": f"Error: {execution_payload['error']}"})
                elif execution_payload["status"] == "blocked":
                    await yield_queue.put({"type": "warning", "content": f"Blocked: {execution_payload['error']}"})
                elif execution_payload["status"] == "HITL_REQUIRED":
                    await yield_queue.put({"type": "warning", "content": f"Authorization Required: {execution_payload['error']}"})
                    # CRITICAL FIX: Force the Synthesizer to understand the task is NOT done
                    synthesizer_prompt += f"\n\n[SYSTEM OVERRIDE]: Tool '{tool.name}' is PENDING. Do NOT claim the task was completed. Relay the authorization request to the user exactly as provided."
                else:
                    await yield_queue.put({"type": "status", "content": f"Tool '{tool.name}' complete."})


        # --- STEP 3: SYNTHESIZE ---
        await yield_queue.put({"type": "status", "content": "Synthesizing final response..."})
        
        async for token in VCore.synthesizer_stream(synthesizer_prompt, tool_results, clean_history):
            await yield_queue.put({"type": "token", "content": token})
            
    except Exception as e:
        await yield_queue.put({"type": "warning", "content": f"System Crash: {str(e)}"})
    finally:
        await yield_queue.put({"type": "done", "content": ""})