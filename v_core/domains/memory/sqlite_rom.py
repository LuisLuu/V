import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class MemoryNode(Base):
    """
    The Universal Container for V's long-term memory.
    Everything is stored as a flexible JSON payload.
    """
    __tablename__ = "memory_nodes"

    # 1. The Primary Keys & Ownership
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True) # Locks data to the specific user

    # 2. The Discriminators (The Bin Labels)
    # Types: "user_fact", "task_log", "active_constraint"
    type = Column(String, nullable=False, index=True) 
    title = Column(String, nullable=True) # A quick human-readable summary

    # 3. The Payload (The Actual Components)
    # This stores the raw unstructured data so we NEVER have to run a database migration.
    payload = Column(JSON, nullable=False) 
    
    # 4. Temporal Data
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Optimize for the Compaction Engine sweeping specific types of memories
    __table_args__ = (
        Index('idx_user_type', 'user_id', 'type'),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "payload": self.payload,
            "timestamp": self.created_at.isoformat()
        }