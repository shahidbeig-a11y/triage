from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base


class UrgencyScore(Base):
    __tablename__ = "urgency_scores"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False, unique=True, index=True)
    urgency_score = Column(Float, nullable=False)  # Final score after escalation and floor
    raw_score = Column(Float, nullable=True)  # Raw score before escalation
    stale_bonus = Column(Integer, default=0)  # Bonus points from stale escalation
    signals_json = Column(Text, nullable=False)  # JSON string with full signal breakdown
    scored_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    floor_override = Column(Boolean, default=False)  # True if score >= urgency floor
    stale_days = Column(Integer, default=0)  # Days since email was received
    force_today = Column(Boolean, default=False)  # True if stale_days >= 11

    # Relationship to email
    email = relationship("Email", back_populates="urgency_score_record")

    def __repr__(self):
        return f"<UrgencyScore(email_id={self.email_id}, score={self.urgency_score})>"
