import sys
import os
import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

# Dynamically add the project root to Python's path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from agents.tools.task_manager import TaskManagerTool

# Define an isolated, disposable test database
TEST_DB_PATH = Path(project_root) / "memory" / "test_rom.db"

class TestTaskManagerCRUD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Build the schema in the isolated test database."""
        conn = sqlite3.connect(TEST_DB_PATH)
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    priority TEXT DEFAULT 'medium'
                )
            ''')
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def tearDownClass(cls):
        """Obliterate the test database file after all tests complete."""
        if TEST_DB_PATH.exists():
            os.remove(TEST_DB_PATH)

    def setUp(self):
        """Initialize the tool and hijack the database path."""
        self.tool = TaskManagerTool()
        # Intercept the tool's DB_PATH and force it to use our test DB
        self.patcher = patch('agents.tools.task_manager.DB_PATH', TEST_DB_PATH)
        self.patcher.start()

    def tearDown(self):
        """Clean out the table after each test to ensure pure isolation."""
        self.patcher.stop()
        conn = sqlite3.connect(TEST_DB_PATH)
        try:
            conn.execute("DELETE FROM tasks")
            conn.commit()
        finally:
            conn.close()

    def test_full_crud_lifecycle(self):
        """Tests Create, Read, Update, and Delete in a continuous flow."""
        
        # --- 1. CREATE ---
        res_create = self.tool.execute(action="create", title="Solder the RF components", priority="high")
        create_data = json.loads(res_create)
        self.assertEqual(create_data["status"], "success")
        
        # Extract ID safely by targeting the end of the specific string structure.
        # (Future upgrade: have execute() return the raw task_id in the JSON so you don't have to parse strings!)
        task_id = int(create_data["message"].split("ID ")[-1].strip("."))
        
        # --- 2. READ ---
        res_read = self.tool.execute(action="read")
        read_data = json.loads(res_read)
        self.assertEqual(read_data["status"], "success")
        self.assertEqual(len(read_data["tasks"]), 1)
        self.assertEqual(read_data["tasks"][0]["id"], task_id)

        # --- 3. UPDATE ---
        res_update = self.tool.execute(action="update", task_id=task_id, status="in_progress")
        update_data = json.loads(res_update)
        self.assertEqual(update_data["status"], "success")
        
        # Verify update actually took effect in the DB
        verify_update = json.loads(self.tool.execute(action="read"))
        self.assertEqual(verify_update["tasks"][0]["status"], "in_progress")

        # --- 4. DELETE ---
        res_delete = self.tool.execute(action="delete", task_id=task_id)
        delete_data = json.loads(res_delete)
        self.assertEqual(delete_data["status"], "success")

        # Verify deletion wiped the row
        verify_delete = json.loads(self.tool.execute(action="read"))
        self.assertNotIn("tasks", verify_delete) 
        self.assertEqual(verify_delete["message"], "No active tasks found.")

    def test_error_handling_hallucinated_id(self):
        """Ensure the system doesn't crash on bad inputs."""
        res_fake_delete = self.tool.execute(action="delete", task_id=9999)
        fake_data = json.loads(res_fake_delete)
        self.assertEqual(fake_data["status"], "failed")
        self.assertIn("not found", fake_data["error"])

if __name__ == "__main__":
    # verbosity=2 gives you a clean, detailed terminal output
    unittest.main(verbosity=2)