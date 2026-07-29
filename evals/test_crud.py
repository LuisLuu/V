import sys
import os
import json

# Dynamically add the project root to Python's path so it can find the 'agents' module
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from agents.tools.task_manager import TaskManagerTool

def run_tests():
    print("🧪 Starting Task Manager CRUD Tests...\n")
    tool = TaskManagerTool()

    # 1. TEST CREATE
    print("--- 1. CREATE ---")
    res_create = tool.execute(action="create", title="Buy Groceries", priority="high")
    print(res_create)
    
    create_data = json.loads(res_create)
    
    if create_data["status"] == "success":
        task_id = int(''.join(filter(str.isdigit, create_data["message"])))
        print(f"Captured Task ID: {task_id}\n")
    else:
        print("Create failed, aborting tests.")
        return

    # 2. TEST READ
    print("--- 2. READ ---")
    res_read = tool.execute(action="read")
    print(f"{res_read}\n")

    # 3. TEST UPDATE
    print("--- 3. UPDATE ---")
    res_update = tool.execute(action="update", task_id=task_id, status="in_progress")
    print(f"{res_update}\n")
    
    print("Read after update:")
    print(f"{tool.execute(action='read')}\n")

    # 4. TEST DELETE
    print("--- 4. DELETE ---")
    res_delete = tool.execute(action="delete", task_id=task_id)
    print(f"{res_delete}\n")

    print("Read after delete:")
    print(f"{tool.execute(action='read')}\n")
    
    # 5. TEST HALLUCINATION/ERROR HANDLING
    print("--- 5. DELETE FAKE ID ---")
    res_fake_delete = tool.execute(action="delete", task_id=9999)
    print(f"{res_fake_delete}\n")

if __name__ == "__main__":
    run_tests()