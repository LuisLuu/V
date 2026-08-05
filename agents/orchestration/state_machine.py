import asyncio
import inspect
import json
from pathlib import Path
import re

from pydantic import ValidationError

from agents.harness.blast_gates import BlastGate
from agents.orchestration.auth_registry import auth_registry
from agents.orchestration.schemas import CognitivePlan
from agents.orchestration.v_core import VCore
from agents.router import MemoryRouter
from agents.tools.system.task_agent import TaskAgent
from agents.tools.tool_registry import registry

# --- Instantiate the Blast Gate ---
security_gate = BlastGate()

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DB_PATH = BASE_DIR / "memory" / "rom.db"

router = MemoryRouter(db_path=str(DB_PATH))

HIGH_RISK_TOOLS = {"command_executor", "terminal_run"}  # Triggers Blast Gate
SAFE_TOOLS = {
    "task_manager",
    "memory_router",
    "conversational_bypass",
}  # Auto-approved


def sanitize_history(history: list) -> list:
    """Non-destructively strips raw tool JSON from the Planner's view of history."""
    clean = []
    for msg in history:
        if msg.get("role") not in ["user", "assistant"]:
            continue
        # Strip out the markdown JSON blocks to prevent the LLM from mimicking past tool calls
        clean_content = re.sub(
            r"```(?:json)?\n?.*?\n?```",
            "[Tool Execution Resolved]",
            msg.get("content", ""),
            flags=re.DOTALL,
        ).strip()
        if clean_content:
            clean.append({"role": msg["role"], "content": clean_content})
    return clean


async def execute_tool_async(tool_name: str, args: dict) -> dict:
    """Secure bridge enforcing BaseTool preconditions and SecurityTiers."""
    if not registry.has_tool(tool_name):
        return {
            "status": "failed",
            "error": f"Tool '{tool_name}' not found in registry.",
        }

    tool_instance = registry.get_tool(tool_name)

    if tool_instance is None:
        return {
            "status": "failed",
            "error": f"Tool '{tool_name}' failed to load.",
        }

    # 1. Hardware/Environment Precondition Check
    if not tool_instance.verify_preconditions():
        return {
            "tool": tool_name,
            "status": "failed",
            "error": "Causal sensors rejected execution.",
        }

    # 2. Security Tier Check via BlastGate (Bypass for Safe Tools)
    if tool_name not in SAFE_TOOLS:
        gate_evaluation = security_gate.evaluate_execution(
            tool_name, tool_instance.security_tier, args
        )

        if not gate_evaluation["approved"]:
            return {
                "tool": tool_name,
                "status": gate_evaluation["status"],
                "error": gate_evaluation.get("ui_prompt")
                or gate_evaluation.get("reason"),
            }

    try:
        # 3. Execution Sandbox
        if inspect.iscoroutinefunction(tool_instance.execute):
            result = await tool_instance.execute(**args)
        else:
            result = await asyncio.to_thread(tool_instance.execute, **args)

        # Universal Error Catcher
        if isinstance(result, dict) and result.get("status") == "error":
            return {
                "tool": tool_name,
                "status": "failed",
                "error": result.get(
                    "message", "Tool execution failed silently."
                ),
            }

        return {"tool": tool_name, "status": "success", "data": result}
    except Exception as e:
        return {"tool": tool_name, "status": "failed", "error": str(e)}


async def run_cognitive_graph(
    prompt: str, yield_queue: asyncio.Queue, chat_history: list
):
    """Executes a strict, loop-free 0-1-2-3 cognitive pipeline."""
    try:
        await yield_queue.put(
            {"type": "status", "content": "Initializing cognitive routing..."}
        )
        tool_results = []

        # --- STEP 0: CONTEXT ROUTING ---
        retrieved_context = None
        if len(prompt.split()) > 3 and len(prompt) > 15:
            retrieved_context = await asyncio.to_thread(
                router.evaluate_and_fetch, prompt
            )

        planner_prompt = prompt
        synthesizer_prompt = prompt

        if retrieved_context:
            memory_injection = f"\n\n[RECALLED PAST MEMORY]: {retrieved_context}"
            planner_prompt += memory_injection
            synthesizer_prompt += memory_injection
            await yield_queue.put(
                {"type": "status", "content": "Context retrieved from ROM."}
            )

        await yield_queue.put(
            {"type": "status", "content": "Syncing Task Ledger..."}
        )
        try:
            task_agent = TaskAgent()
            all_tasks = await asyncio.to_thread(task_agent.list_tasks)

            active_tasks = [
                t for t in all_tasks if t["status"] in ["pending", "in_progress"]
            ]

            task_list_str = ""
            if active_tasks:
                task_list_str = "\n".join(
                    [
                        f"- [ID: {t['id']}] {t['title']} (Status: {t['status']})"
                        for t in active_tasks
                    ]
                )
            else:
                task_list_str = "No active tasks."

            state_injection = f"\n\n[CURRENT SYSTEM TASKS]:\n{task_list_str}"
            state_injection += "\n[CRITICAL RULE]: When asked to update or delete a task without an explicit ID, you must use the chat history to deduce which task the user means, find its ID in the list above, and INCLUDE the integer in your tool call."
            state_injection += "\n[BATCH PROCESSING RULE]: If the user updates or mentions multiple tasks in a single sentence (e.g., 'I bought the chicken and the tree'), you MUST output a separate tool call for EACH item in the 'tool_calls' array. Never ignore secondary items."
            
            # 1. ONLY feed active tasks to the Planner for routing execution
            planner_prompt += "\n[CRITICAL RULE]: If the user asks a general knowledge, research, or comparative question (e.g., hardware differences, definitions), DO NOT use local file system tools. Proceed with an empty tool plan and synthesize the answer from your training data or a web search."
            planner_prompt += state_injection

            # Do NOT attach state_injection to synthesizer_prompt! Keeps V from nagging.
        except Exception as e:
            await yield_queue.put(
                {"type": "warning", "content": f"Ledger Sync Failed: {e}"}
            )

        # --- STEP 1: PLAN ---
        await yield_queue.put(
            {"type": "status", "content": "Planning execution path..."}
        )

        clean_history = sanitize_history(chat_history)
        plan_payload = await VCore.planner_llm_call(
            planner_prompt, tool_results, clean_history
        )

        try:
            clean_payload = re.sub(
                r"```(?:json)?\n?(.*?)\n?```",
                r"\1",
                plan_payload,
                flags=re.DOTALL,
            ).strip()

            validated_plan = CognitivePlan.model_validate_json(clean_payload)

        except ValidationError as e:
            # Send technical detail to the dev logs/UI, but hide raw stack trace from Synthesizer
            await yield_queue.put({"type": "warning", "content": f"Planner schema validation failed: {str(e)}"})
            validated_plan = CognitivePlan(tool_calls=[])
            tool_results.append({"status": "failed", "error": "Planner execution failed internally."})
        except json.JSONDecodeError:
            await yield_queue.put({"type": "warning", "content": "Planner output invalid JSON."})
            validated_plan = CognitivePlan(tool_calls=[])
            tool_results.append({"status": "failed", "error": "Planner execution failed internally."})

        if validated_plan.tool_calls:
            MAX_TOOLS = 3
            if len(validated_plan.tool_calls) > MAX_TOOLS:
                warning_msg = f"System Overload: Truncating requested tools to {MAX_TOOLS}."
                await yield_queue.put({"type": "warning", "content": warning_msg})
                tool_results.append(
                    {
                        "status": "system_warning",
                        "message": warning_msg,
                        "dropped_tasks": len(validated_plan.tool_calls) - MAX_TOOLS,
                    }
                )
                validated_plan.tool_calls = validated_plan.tool_calls[:MAX_TOOLS]

            for tool in validated_plan.tool_calls:
                sanitized_args = {}
                for key, value in tool.args.items():
                    sanitized_args[key] = (
                        value[0]
                        if isinstance(value, list) and len(value) == 1
                        else value
                    )

                if tool.name == "draft_memory_update":
                    draft_text = str(sanitized_args).lower()
                    transient_words = [
                        "today",
                        "now",
                        "tomorrow",
                        "tonight",
                        "currently",
                        "just now",
                    ]
                    if any(word in draft_text for word in transient_words):
                        await yield_queue.put(
                            {
                                "type": "warning",
                                "content": "Memory Bank rejected temporary temporal statement. Bypassing tool.",
                            }
                        )
                        continue

                await yield_queue.put(
                    {
                        "type": "status",
                        "content": f"Evaluating {tool.name} safety...",
                    }
                )

                tool_instance = registry.get_tool(tool.name)
                if not tool_instance:
                    tool_results.append(
                        {
                            "tool": tool.name,
                            "status": "failed",
                            "error": "Tool not found.",
                        }
                    )
                    continue

                gate_evaluation = security_gate.evaluate_execution(
                    tool.name, tool_instance.security_tier, sanitized_args
                )

                if gate_evaluation["status"] == "HITL_REQUIRED":
                    command_str = str(sanitized_args)
                    action_id = auth_registry.create_action(command_str)

                    await yield_queue.put(
                        {
                            "type": "auth_request",
                            "action_id": action_id,
                            "command": command_str,
                        }
                    )

                    approved = await auth_registry.wait_for_approval(action_id)

                    if not approved:
                        await yield_queue.put(
                            {
                                "type": "warning",
                                "content": f"Execution of '{tool.name}' denied.",
                            }
                        )
                        tool_results.append(
                            {
                                "tool": tool.name,
                                "status": "blocked",
                                "error": "User denied authorization.",
                            }
                        )
                        continue

                elif not gate_evaluation["approved"]:
                    tool_results.append(
                        {
                            "tool": tool.name,
                            "status": "blocked",
                            "error": gate_evaluation.get("reason", "Unknown block"),
                        }
                    )
                    continue

                execution_payload = await execute_tool_async(
                    tool.name, sanitized_args
                )

                if (
                    tool.name == "task_manager"
                    and execution_payload["status"] == "success"
                ):
                    await yield_queue.put({"type": "task_update"})

                # 2. SILENT MEMORY CONFIRMATION: Tell the engine to save silently
                if (
                    tool.name == "draft_memory_update"
                    and execution_payload["status"] == "success"
                ):
                    draft_text = execution_payload.get("data", "")
                    draft_text = (
                        draft_text.replace("__MEMORY_DRAFT__:", "")
                        .replace("__MEMORY_DRAFT__", "")
                        .strip()
                    )
                    await yield_queue.put(
                        {"type": "memory_draft", "content": draft_text}
                    )
                    execution_payload[
                        "data"
                    ] = "System Notification: Memory saved to ROM silently. Continue conversational turn naturally without explicitly telling the user you saved a memory."

                tool_results.append(execution_payload)

                if execution_payload["status"] == "failed":
                    await yield_queue.put(
                        {
                            "type": "warning",
                            "content": f"Error: {execution_payload['error']}",
                        }
                    )
                elif execution_payload["status"] == "blocked":
                    await yield_queue.put(
                        {
                            "type": "warning",
                            "content": f"Blocked: {execution_payload['error']}",
                        }
                    )
                elif execution_payload["status"] == "HITL_REQUIRED":
                    await yield_queue.put(
                        {
                            "type": "warning",
                            "content": f"Authorization Required: {execution_payload['error']}",
                        }
                    )
                    synthesizer_prompt += f"\n\n[SYSTEM OVERRIDE]: Tool '{tool.name}' is PENDING. Do NOT claim the task was completed. Relay the authorization request to the user exactly as provided."
                else:
                    await yield_queue.put(
                        {
                            "type": "status",
                            "content": f"Tool '{tool.name}' complete.",
                        }
                    )

        # --- STEP 3: SYNTHESIZE ---
        # 3. CONVICTION & OMERTA DIRECTIVES
        synthesizer_prompt += "\n\n[CRITICAL RULE]: You speak directly to the user as a grounded engineer. NEVER mention memory updates, dynamic memory, task lists, or tool executions unless explicitly asked."
        synthesizer_prompt += "\n[CRITICAL RULE]: If a tool error occurs, handle it gracefully without mentioning JSON schemas, code validation errors, or internal architecture details."
        synthesizer_prompt += "\n[CRITICAL RULE]: If no explicit URL or search data is provided in the tool execution payload, synthesize a natural conversational response WITHOUT citing any sources or using placeholders like [Source Name] or [insert temp]."

        await yield_queue.put(
            {"type": "status", "content": "Synthesizing final response..."}
        )

        buffer = ""
        trigger_words = [
            "__MEMORY_DRAFT__",
            "MEMORY_DRAFT:",
            "MEMORY_DRAFT",
        ]

        async for token in VCore.synthesizer_stream(
            synthesizer_prompt, tool_results, clean_history
        ):
            buffer += token

            if any(trigger in buffer for trigger in trigger_words):
                for trigger in trigger_words:
                    buffer = buffer.replace(trigger, "")
                continue

            is_partial_match = False
            for trigger in trigger_words:
                for i in range(1, len(trigger)):
                    if buffer.endswith(trigger[:i]):
                        is_partial_match = True
                        break
                if is_partial_match:
                    break

            if not is_partial_match:
                await yield_queue.put({"type": "token", "content": buffer})
                buffer = ""

        if buffer:
            await yield_queue.put({"type": "token", "content": buffer})

    except Exception as e:
        await yield_queue.put(
            {"type": "warning", "content": f"System Crash: {str(e)}"}
        )
    finally:
        await yield_queue.put({"type": "done", "content": ""})