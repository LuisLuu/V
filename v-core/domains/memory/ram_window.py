from typing import List, Dict

class RAMWindow:
    """
    V's immediate working memory. 
    Strictly bounded to prevent context rot and latency spikes.
    """
    def __init__(self, max_interactions: int = 10):
        # Define a strict limit before triggering compaction
        self.max_interactions = max_interactions
        self.system_prompt: Dict = {}
        
        # Everything currently active
        self.active_messages: List[Dict] = []

    def set_system_index(self, index_text: str):
        """
        Loads the lightweight tool index. Phase 1 of Progressive Disclosure.
        """
        self.system_prompt = {"role": "system", "content": index_text}

    def append_node(self, role: str, content: str, status: str = "active"):
        """
        Adds a new message to RAM, attaching the metadata tag needed
        by the Compaction Engine later.
        """
        node = {
            "role": role,
            "content": content,
            "status": status  # "active", "completed", or "ephemeral"
        }
        self.active_messages.append(node)

    def is_critical(self) -> bool:
        """
        A fast computational sensor. 
        Returns True if the desk is getting too cluttered.
        """
        return len(self.active_messages) >= self.max_interactions

    def get_working_context(self) -> List[Dict]:
        """
        Assembles the exact payload sent to Qwen 2.5.
        """
        # Always inject the system instructions first
        context = [self.system_prompt] if self.system_prompt else []
        
        # Append the raw text of the active session
        context.extend(self.active_messages)
        return context
        
    def clear_compacted_nodes(self, remaining_nodes: List[Dict]):
        """
        Called by the Compaction Engine after a sweep.
        Replaces the cluttered RAM with the condensed state.
        """
        self.active_messages = remaining_nodes