"""
Database models — SQLAlchemy ORM.
Replaces the JSON-file-based metadata storage in storage/metadata/.
"""
import os
import uuid
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Integer, DateTime, Text, Boolean, JSON, ForeignKey
)
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local_fallback.db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Document(Base):
    __tablename__ = "documents"

    doc_id = Column(String, primary_key=True)        # sha256 hash
    user_id = Column(String, ForeignKey("users.id"), nullable=True)  # NULL = public/demo doc
    filename = Column(String, nullable=False)
    file_ext = Column(String, nullable=False)
    file_size_bytes = Column(Integer, default=0)
    page_count = Column(Integer, default=0)
    status = Column(String, default="queued")          # queued|parsing|classifying|indexing|indexed|error
    error_message = Column(Text, nullable=True)
    classification = Column(JSON, nullable=True)        # type, topic, sensitivity, etc.
    chunk_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    indexed_at = Column(DateTime, nullable=True)


def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    Base.metadata.create_all(bind=engine)


def get_session():
    return SessionLocal()