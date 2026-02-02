from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from ..database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(Integer, unique=True, nullable=False)
    label = Column(String, nullable=False)
    tab = Column(String, nullable=False)  # e.g., "P1", "P2", "Action"
    description = Column(String)
    is_system = Column(Boolean, default=False)
    icon = Column(String)  # emoji or icon name
    color = Column(String)  # hex color code

    # Relationship to emails
    emails = relationship("Email", back_populates="category")

    def __repr__(self):
        return f"<Category(number={self.number}, label='{self.label}', tab='{self.tab}')>"
