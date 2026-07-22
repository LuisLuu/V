import os
import sqlite3
import logging
from pathlib import Path
from contextlib import closing
from typing import List, Dict, Any

# Configure a localized logger for the memory domain
logger = logging.getLogger("v_core.memory")

# Match the exact pathing logic from state_machine.py
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_DB_PATH = str(BASE_DIR / "data" / "rom.db")

class SQLiteROM:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with closing(self._get_connection()) as conn:
            # 1. Execute PRAGMAs outside the transaction block to actually enable WAL
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            
            # 2. Start the transaction for table/trigger creation
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
        with closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT c.id, c.content, c.tags, c.timestamp 
                   FROM chat_search_idx s
                   JOIN chat_logs c ON s.rowid = c.id
                   WHERE s.chat_search_idx MATCH ? 
                   ORDER BY s.rank LIMIT 5""",
                (f"{search_query}*",)
            )
            results = [dict(row) for row in cursor.fetchall()]
            
            logger.info(f"[ROM SEARCH] Query: '{search_query}' yielded {len(results)} hits.")
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