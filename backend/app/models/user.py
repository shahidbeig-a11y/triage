from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from ..database import Base


class User(Base):
    """
    User model for storing OAuth tokens and user information.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String)

    # OAuth tokens
    access_token = Column(String)
    refresh_token = Column(String)
    token_expires_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
