from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base


class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String, unique=True, index=True, nullable=False)
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

    # Status fields
    folder = Column(String, default="inbox")  # inbox, archive, deleted
    status = Column(String, default="unprocessed")  # unprocessed, processed, archived

    def __repr__(self):
        return f"<Email(id={self.id}, subject='{self.subject}', from='{self.from_address}')>"
