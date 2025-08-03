from sqlalchemy import Column, Integer, String, create_engine, JSON
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# ========== Database Setup ==========

DATABASE_URL = "sqlite:///./test.db"  # Use relative path for SQLite

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# ========== Model Definition ==========

class TemplateModel(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    data = Column(JSON, nullable=False)  # JSON column
    img_count = Column(Integer, default=0)
    text_count = Column(Integer, default=0)

# ========== Create Tables ==========

Base.metadata.create_all(bind=engine)

# ========== FastAPI Setup ==========
# Dependency: Get DB session per request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# pydantic stuff
from pydantic import BaseModel, Field
from typing import List, Optional

class Realtor(BaseModel):
    name: Optional[str]
    address: Optional[str]
    email: Optional[str]
    photo: Optional[str] = None

class Template(BaseModel):
    template_name: str
    realtor: Optional[Realtor]
    logos: Optional[List[str]] = Field(default_factory=list)
    property_images: Optional[List[str]] = Field(default_factory=list)
    text_fields: Optional[List[str]] = Field(default_factory=list)
