from sqlalchemy import Column, Integer, Float, String
from ..database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    task_limit = Column(Integer, default=5)  # Max number of tasks to show
    urgency_floor = Column(Float, default=0.3)  # Minimum urgency score to display
    ai_threshold = Column(Float, default=0.7)  # Confidence threshold for auto-classification
    tone_exclusions = Column(String)  # JSON string of excluded tone keywords

    def __repr__(self):
        return f"<UserSettings(id={self.id}, task_limit={self.task_limit})>"
