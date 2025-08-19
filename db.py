from sqlalchemy import Column, Integer, String, create_engine, JSON, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, Session, relationship

# ========== Database Setup ==========

DATABASE_URL = "sqlite:///./test.db"  # Use relative path for SQLite

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# ========== Model Definition ==========

class TemplateModel(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    template_name = Column(String, nullable=False, unique=True, index=True)
    output = Column(String, nullable=False)
    realtor_name = Column(String, nullable=True)
    realtor_info = Column(String, nullable=True)
    realtor_photo = Column(String, nullable=True)

    # Simple arrays — use PostgreSQL JSONB or ARRAY if supported
    logos = Column(JSON, nullable=False, default=list)
    property_images = Column(JSON, nullable=False, default=list)

    # Stats (optional convenience columns)
    img_count = Column(Integer, default=0)
    text_count = Column(Integer, default=0)

    # Relationship: one template → many text fields
    text_fields = relationship("TextFieldModel", back_populates="template", cascade="all, delete-orphan")


class TextFieldModel(Base):
    __tablename__ = "text_fields"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("templates.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)               # e.g. "text_headline"
    approx_length = Column(Integer, nullable=False)     # e.g. 30
    format = Column(String, nullable=False)             # e.g. "Spacious Family Home..."

    template = relationship("TemplateModel", back_populates="text_fields")

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
from typing import List, Optional, Dict


class Realtor(BaseModel):
    name: Optional[str]
    info: Optional[str]
    photo: Optional[str] = None

class TextFieldSpec(BaseModel):
    approx_length: int = Field(..., gt=0, description="Recommended character length (>0)")
    format: str = Field(..., min_length=1, description="Example string for this field")



class Template(BaseModel):
    template_name: str
    realtor: Optional[Realtor] = None
    output: str
    logos: List[str] = Field(default_factory=list)
    property_images: List[str] = Field(default_factory=list)
    text_fields: Dict[str, TextFieldSpec] = Field(..., min_items=1)
