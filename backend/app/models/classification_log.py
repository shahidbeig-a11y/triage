from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from datetime import datetime
from ..database import Base


class ClassificationLog(Base):
    """
    Log of email classification events.

    Tracks every classification attempt (deterministic or AI) for auditing
    and debugging purposes.
    """
    __tablename__ = "classification_log"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    rule = Column(String, nullable=True)  # Description of rule that matched
    classifier_type = Column(String, nullable=False)  # 'deterministic' or 'ai'
    confidence = Column(Float, nullable=False)  # 0.0 to 1.0
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ClassificationLog(email_id={self.email_id}, category_id={self.category_id}, type='{self.classifier_type}')>"
