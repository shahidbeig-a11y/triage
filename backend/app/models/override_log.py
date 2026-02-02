from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from ..database import Base


class OverrideLog(Base):
    """
    Log of classification override events.

    Tracks when emails classified into Other categories (6-11) are overridden
    back to Work pipeline due to urgency, VIP sender, or personal direction.
    """
    __tablename__ = "override_log"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False, index=True)
    original_category = Column(Integer, ForeignKey("categories.id"), nullable=False)
    trigger_type = Column(String, nullable=False)  # urgency_language, vip_sender, etc.
    reason = Column(String, nullable=False)  # Human-readable explanation
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<OverrideLog(email_id={self.email_id}, trigger='{self.trigger_type}')>"
