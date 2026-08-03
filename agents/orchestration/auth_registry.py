import asyncio
from typing import Any, Dict
import uuid


class AuthRegistry:
    def __init__(self):
        self._pending: Dict[str, Dict[str, Any]] = {}

    def create_action(self, command: str) -> str:
        """Creates a pending action with a unique ID and an asyncio event lock."""
        action_id = str(uuid.uuid4())
        self._pending[action_id] = {
            "event": asyncio.Event(),
            "approved": False,
            "command": command,
        }
        return action_id

    async def wait_for_approval(self, action_id: str) -> bool:
        """Pauses the calling task until event.set() is triggered by the API."""
        if action_id not in self._pending:
            return False

        event = self._pending[action_id]["event"]
        await event.wait()  # <--- THE ENGINE PAUSES HERE

        approved = self._pending[action_id]["approved"]
        del self._pending[action_id]  # Clean up memory after resumption
        return approved

    def resolve_action(self, action_id: str, approved: bool) -> bool:
        """Called by the API route to unlock the paused state machine task."""
        if action_id in self._pending:
            self._pending[action_id]["approved"] = approved
            self._pending[action_id]["event"].set()  # <--- THE ENGINE RESUMES HERE
            return True
        return False


# Single shared instance across your backend app
auth_registry = AuthRegistry()