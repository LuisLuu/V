import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from v_core.domains.memory.sqlite_rom import SQLiteROM
from v_core.domains.tools.system.task_agent import TaskAgent

def test_task_agent_flow():
    print("--- Initializing ROM & TaskAgent ---")
    rom = SQLiteROM()  # Uses default DB path
    agent = TaskAgent(rom=rom)

    # 1. Create a task
    res_create = agent.create_task(
        title="Fix TWAI driver bug", 
        description="Investigate bus recovery logic.", 
        priority="high"
    )
    print("Create:", res_create)
    task_id = res_create.get("task_id")

    # 2. List tasks
    pending_tasks = agent.list_tasks(status_filter="pending")
    print(f"Pending Tasks ({len(pending_tasks)}):", pending_tasks)

    # 3. Update task status & check timestamp trigger
    if task_id:
        res_update = agent.update_task(task_id=task_id, status="in_progress")
        print("Update:", res_update)

        # Re-fetch task to verify updated_at trigger
        all_tasks = agent.list_tasks()
        updated_task = next((t for t in all_tasks if t["id"] == task_id), None)
        print("Updated Task Row:", updated_task)

if __name__ == "__main__":
    test_task_agent_flow()