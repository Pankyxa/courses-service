from sqlalchemy import Column, Integer, String, Text

from src.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    author = Column(String(100), nullable=True)
    duration_hours = Column(Integer, nullable=True)
