from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base


class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String, unique=True, index=True, nullable=False)
    immutable_id = Column(String, unique=True, index=True, nullable=True)  # Stays constant across folder moves
    from_address = Column(String, nullable=False)
    from_name = Column(String)
    subject = Column(String)
    body_preview = Column(String)
    body = Column(Text)  # Full HTML body
    received_at = Column(DateTime, default=datetime.utcnow)
    importance = Column(String)  # low, normal, high
    conversation_id = Column(String, index=True)
    has_attachments = Column(Boolean, default=False)
    is_read = Column(Boolean, default=False)
    to_recipients = Column(Text)  # JSON string of recipients
    cc_recipients = Column(Text)  # JSON string of recipients

    # Classification fields
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", back_populates="emails")
    confidence = Column(Float)  # 0.0 to 1.0
    urgency_score = Column(Float)  # 0.0 to 1.0
    due_date = Column(DateTime, nullable=True)
    todo_task_id = Column(String, nullable=True)  # Microsoft To-Do task ID
    assigned_to = Column(String, nullable=True)  # Person name for Discuss/Delegate
    duration_estimate = Column(Integer, default=30)  # AI-estimated duration in minutes

    # Timing fields for calibration
    approved_at = Column(DateTime, nullable=True)  # When user approved
    executed_at = Column(DateTime, nullable=True)  # When user executed/completed

    # Urgency score relationship
    urgency_score_record = relationship("UrgencyScore", back_populates="email", uselist=False)

    # Status fields
    folder = Column(String, default="inbox")  # inbox, archive, deleted
    status = Column(String, default="unprocessed")  # unprocessed, processed, archived

    # Folder intelligence (for FYI - Group emails)
    recommended_folder = Column(String, nullable=True)  # AI-recommended folder
    folder_is_new = Column(Boolean, default=False)  # Whether folder needs to be created

    def __repr__(self):
        return f"<Email(id={self.id}, subject='{self.subject}', from='{self.from_address}')>"
