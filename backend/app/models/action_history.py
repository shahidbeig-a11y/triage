from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from datetime import datetime
from ..database import Base


class ActionHistory(Base):
    __tablename__ = "action_history"

    id = Column(Integer, primary_key=True, index=True)
    action_type = Column(String, nullable=False)  # approve, execute, reclassify, etc.
    description = Column(String, nullable=False)  # Human-readable description
    action_data = Column(Text, nullable=False)  # JSON with all data needed to undo
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    def __repr__(self):
        return f"<ActionHistory(id={self.id}, type='{self.action_type}', desc='{self.description}')>"
