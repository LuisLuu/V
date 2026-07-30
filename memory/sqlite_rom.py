import os
import sqlite3
import logging
import bcrypt
import re
import uuid

from pathlib import Path
from contextlib import closing
from typing import List, Dict, Any

# 1. Strictly define the absolute path based on this file's location in the memory folder
MEMORY_DIR = Path(__file__).resolve().parent
ABSOLUTE_DB_PATH = str(MEMORY_DIR / "rom.db")
logger = logging.getLogger("v_core.memory")

class SQLiteROM:
    # 2. Change the signature to capture any passed db_path, but IGNORE IT.
    def __init__(self, db_path=None): 
        # Force the absolute path, preventing VCore or other classes from injecting a bad relative path
        self.db_path = ABSOLUTE_DB_PATH
        
        # This will now always safely build the correct memory directory
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self):
        
        # print(f"\n[CRITICAL DEBUG] Attempting to open DB at: {self.db_path}\n")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with closing(self._get_connection()) as conn:
            # 1. Execute PRAGMAs outside the transaction block to actually enable WAL
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            
            with conn: 
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chat_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        tags TEXT DEFAULT '',
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS chat_search_idx USING fts5(
                        content,
                        tags,
                        content='chat_logs',
                        content_rowid='id',
                        tokenize='porter'
                    )
                """)
                
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS after_chat_logs_insert 
                    AFTER INSERT ON chat_logs BEGIN
                        INSERT INTO chat_search_idx(rowid, content, tags) 
                        VALUES (new.id, new.content, new.tags);
                    END
                """)
                
                # 3. Correct FTS5 Update Logic: Delete old index, insert new index
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS before_chat_logs_update 
                    BEFORE UPDATE OF tags ON chat_logs BEGIN
                        INSERT INTO chat_search_idx(chat_search_idx, rowid, content, tags) 
                        VALUES ('delete', old.id, old.content, old.tags);
                    END
                """)

                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS after_chat_logs_update 
                    AFTER UPDATE OF tags ON chat_logs BEGIN
                        INSERT INTO chat_search_idx(rowid, content, tags) 
                        VALUES (new.id, new.content, new.tags);
                    END
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY,
                        title TEXT DEFAULT 'New Chat',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cursor.execute("""
                        CREATE TRIGGER IF NOT EXISTS after_sessions_update 
                        AFTER UPDATE ON sessions 
                        WHEN old.updated_at = new.updated_at 
                        BEGIN
                            UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                        END;
                    """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        description TEXT,
                        status TEXT CHECK(status IN ('pending', 'in_progress', 'completed', 'cancelled')) DEFAULT 'pending',
                        priority TEXT CHECK(priority IN ('low', 'medium', 'high')) DEFAULT 'medium',
                        deadline TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS after_tasks_update 
                    AFTER UPDATE ON tasks 
                    WHEN old.updated_at = new.updated_at 
                    BEGIN
                        UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END;
                """)           

                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS before_chat_logs_delete 
                    BEFORE DELETE ON chat_logs BEGIN
                        INSERT INTO chat_search_idx(chat_search_idx, rowid, content, tags) 
                        VALUES ('delete', old.id, old.content, old.tags);
                    END
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS system_auth (
                        id INTEGER PRIMARY KEY CHECK (id = 1), -- Forces only a single row (the master PIN)
                        pin_hash TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
        logger.info(f"SQLite ROM database initialized at {self.db_path} and schemas verified.")

    def save_message(self, session_id: str, role: str, content: str, tags: str = "") -> int | None:
        """Persists a single message segment into the long-term memory layer."""
        with closing(self._get_connection()) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO chat_logs (session_id, role, content, tags) VALUES (?, ?, ?, ?)",
                    (session_id, role, content, tags)
                )
                row_id = cursor.lastrowid
                
            logger.info(f"[ROM WRITE] Success. Session: {session_id} | RowID: {row_id} | Tags: [{tags}]")
            return row_id

    def get_recent_context(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves chronological exact context for the sliding window."""
        with closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            # Added 'id' to the SELECT statement
            cursor.execute(
                """SELECT id, role, content FROM chat_logs 
                   WHERE session_id = ? 
                   ORDER BY timestamp DESC LIMIT ?""",
                (session_id, limit)
            )
            rows = cursor.fetchall()
            # Include the id in the returned dictionary
            context = [{"id": row["id"], "role": row["role"], "content": row["content"]} for row in reversed(rows)]
            
            logger.debug(f"[ROM READ] Fetched {len(context)} rows for context window.")
            return context

    def vague_search(self, search_query: str) -> List[Dict[str, Any]]:
        """Executes a full-text semantic-style match against content and tagged categories."""
        # Strip out any punctuation (like '?' or '!') that breaks FTS5 syntax
        safe_query = re.sub(r'[^\w\s]', '', search_query).strip()
        match_str = f"{safe_query}*" if safe_query else "*"

        with closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT c.id, c.content, c.tags, c.timestamp 
                   FROM chat_search_idx s
                   JOIN chat_logs c ON s.rowid = c.id
                   WHERE s.chat_search_idx MATCH ? 
                   ORDER BY s.rank LIMIT 5""",
                (match_str,)
            )
            results = [dict(row) for row in cursor.fetchall()]
            
            logger.info(f"[ROM SEARCH] Query: '{safe_query}' yielded {len(results)} hits.")
            return results
        
    def update_tags(self, row_id: int, tags: str):
        """Updates the tag column for an existing message without duplicating it."""
        from contextlib import closing
        with closing(self._get_connection()) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE chat_logs SET tags = ? WHERE id = ?",
                    (tags, row_id)
                )
        logger.info(f"[ROM UPDATE] Tags added to RowID: {row_id} | Tags: [{tags}]")

    def enforce_capacity_limit(self, max_rows: int = 10000):
        """
        Acts as an LRU (Least Recently Used) cache limit rather than a strict chronological wipe.
        We archive data until it hits a physical ceiling, preventing artificial amnesia.
        """
        from contextlib import closing
        
        with closing(self._get_connection()) as conn:
            with conn: 
                cursor = conn.cursor()
                
                # Delete oldest rows ONLY if we exceed the physical row threshold
                cursor.execute(
                    f"""
                    DELETE FROM chat_logs 
                    WHERE id NOT IN (
                        SELECT id FROM chat_logs ORDER BY timestamp DESC LIMIT {max_rows}
                    )
                    """
                )
                deleted_count = cursor.rowcount
                
        if deleted_count > 0:
            logger.info(f"🧹 [ROM MAINTENANCE] Archived and pruned {deleted_count} oldest rows to maintain {max_rows} limit.")

    def setup_master_pin(self, raw_pin: str):
        """Hashes and stores the master PIN. Overwrites if one exists."""
        salt = bcrypt.gensalt()
        pin_hash = bcrypt.hashpw(raw_pin.encode('utf-8'), salt).decode('utf-8')
        
        with self._get_connection() as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO system_auth (id, pin_hash) VALUES (1, ?)", 
                    (pin_hash,)
                )
        logger.info("Master PIN successfully set/updated.")

    def verify_master_pin(self, raw_pin: str) -> bool:
        """Checks a provided PIN against the stored hash."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT pin_hash FROM system_auth WHERE id = 1")
            row = cursor.fetchone()
            
        if not row:
            return False # No PIN set yet
            
        stored_hash = row["pin_hash"].encode('utf-8')
        return bcrypt.checkpw(raw_pin.encode('utf-8'), stored_hash)

    def create_session(self, initial_title: str = "New Chat") -> str:
        """Generates a unique session ID and registers it in the ROM."""
        session_id = str(uuid.uuid4())
        with closing(self._get_connection()) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO sessions (id, title) VALUES (?, ?)",
                    (session_id, initial_title)
                )
        logger.info(f"[ROM WRITE] Session created: {session_id}")
        return session_id

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Retrieves all sessions ordered by most recently updated."""
        with closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, updated_at FROM sessions ORDER BY updated_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def update_session_title(self, session_id: str, new_title: str):
        """Updates the session title (usually called via background LLM task)."""
        with closing(self._get_connection()) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE sessions SET title = ? WHERE id = ?",
                    (new_title, session_id)
                )
        logger.info(f"[ROM UPDATE] Session {session_id} renamed to '{new_title}'")

    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieves the full chronological chat history for the frontend UI."""
        from contextlib import closing
        with closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            # Fetch oldest to newest for UI rendering
            cursor.execute(
                "SELECT role, content FROM chat_logs WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_session(self, session_id: str):
        """Deletes a session and permanently wipes its associated chat logs."""
        from contextlib import closing
        with closing(self._get_connection()) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM chat_logs WHERE session_id = ?", (session_id,))
                cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        logger.info(f"🧹 [ROM DELETE] Session and logs wiped for: {session_id}")