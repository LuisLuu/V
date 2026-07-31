import sqlite3
import unittest
import os
from pathlib import Path

# Target an isolated test database
TEST_DB_PATH = Path(os.path.dirname(os.path.abspath(__file__))).parent / "memory" / "core_db_test.db"

class TestDatabaseCore(unittest.TestCase):
    def setUp(self):
        """Set up a fresh database connection and schema before every single test."""
        TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(TEST_DB_PATH)
        self.conn.row_factory = sqlite3.Row  # Allows accessing columns by name
        self.cursor = self.conn.cursor()
        
        # Build the exact production schema
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                priority TEXT DEFAULT 'medium',
                deadline TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def tearDown(self):
        """Close connections and nuke the database file."""
        self.conn.close()
        if TEST_DB_PATH.exists():
            try:
                os.remove(TEST_DB_PATH)
            except PermissionError:
                pass

    def test_direct_sql_crud(self):
        """Tests the raw SQL queries for Create, Read, Update, and Delete."""
        
        # 1. CREATE
        self.cursor.execute(
            "INSERT INTO tasks (title, priority) VALUES (?, ?)", 
            ("Calibrate 3D printer enclosure", "high")
        )
        self.conn.commit()
        task_id = self.cursor.lastrowid
        self.assertIsNotNone(task_id, "Database failed to generate an auto-incrementing ID.")

        # 2. READ
        self.cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = self.cursor.fetchone()
        self.assertIsNotNone(row, "Failed to retrieve the inserted record.")
        self.assertEqual(row["title"], "Calibrate 3D printer enclosure")
        self.assertEqual(row["status"], "pending") # Checking default value application

        # 3. UPDATE
        self.cursor.execute(
            "UPDATE tasks SET status = ? WHERE id = ?", 
            ("completed", task_id)
        )
        self.conn.commit()
        
        self.cursor.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
        updated_row = self.cursor.fetchone()
        self.assertEqual(updated_row["status"], "completed", "Database update operation failed.")

        # 4. DELETE
        self.cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()
        
        self.cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        deleted_row = self.cursor.fetchone()
        self.assertIsNone(deleted_row, "Record still exists after DELETE operation.")

if __name__ == "__main__":
    unittest.main(verbosity=2)