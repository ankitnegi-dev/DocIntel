"""
Document Repository
--------------------
Postgres-backed replacement for the old storage/metadata/*.json files.
Falls back gracefully if DATABASE_URL isn't set (shouldn't happen in prod).
"""
import logging
from datetime import datetime
from typing import Optional

from models.db import get_session, Document, User
from services.auth import hash_password

logger = logging.getLogger(__name__)


# ── Documents ────────────────────────────────────────────────────────────────

def get_document(doc_id: str) -> Optional[dict]:
    """Fetch a document record by doc_id. Returns None if not found."""
    session = get_session()
    try:
        doc = session.get(Document, doc_id)
        if doc is None:
            return None
        return {
            "doc_id": doc.doc_id,
            "user_id": doc.user_id,
            "original_filename": doc.filename,
            "file_ext": doc.file_ext,
            "file_size": doc.file_size_bytes,
            "page_count": doc.page_count,
            "status": doc.status,
            "error_message": doc.error_message,
            "classification": doc.classification,
            "chunk_count": doc.chunk_count,
            "upload_time": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "indexed_at": doc.indexed_at.isoformat() if doc.indexed_at else None,
        }
    finally:
        session.close()


def upsert_document(
    doc_id: str,
    filename: str,
    file_ext: str,
    file_size: int,
    status: str,
    page_count: int = 0,
    classification: dict | None = None,
    chunk_count: int = 0,
    error_message: str | None = None,
    user_id: str | None = None,
) -> None:
    """Insert or update a document record. user_id=None means a public/demo document."""
    session = get_session()
    try:
        doc = session.get(Document, doc_id)
        if doc is None:
            doc = Document(doc_id=doc_id, filename=filename, file_ext=file_ext, user_id=user_id)
            session.add(doc)

        doc.filename = filename
        doc.file_ext = file_ext
        doc.file_size_bytes = file_size
        doc.status = status
        doc.page_count = page_count
        doc.classification = classification
        doc.chunk_count = chunk_count
        doc.error_message = error_message
        # Only set user_id on first creation; never overwrite ownership on re-upload/reindex
        if doc.user_id is None and user_id is not None:
            doc.user_id = user_id

        if status == "indexed" and doc.indexed_at is None:
            doc.indexed_at = datetime.utcnow()

        session.commit()
    except Exception as e:
        logger.error(f"upsert_document failed for {doc_id}: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def list_documents(user_id: str | None = None) -> list[dict]:
    """
    Return document records, most recent first.
    If user_id is given: returns that user's documents PLUS public (user_id IS NULL) documents.
    If user_id is None: returns only public documents (anonymous/demo view).
    """
    session = get_session()
    try:
        query = session.query(Document)
        if user_id is not None:
            query = query.filter(
                (Document.user_id == user_id) | (Document.user_id.is_(None))
            )
        else:
            query = query.filter(Document.user_id.is_(None))

        docs = query.order_by(Document.uploaded_at.desc()).all()
        return [
            {
                "doc_id": d.doc_id,
                "user_id": d.user_id,
                "original_filename": d.filename,
                "page_count": d.page_count,
                "status": d.status,
                "classification": d.classification,
                "chunk_count": d.chunk_count,
                "upload_time": d.uploaded_at.isoformat() if d.uploaded_at else None,
            }
            for d in docs
        ]
    finally:
        session.close()



def get_visible_doc_ids(user_id: str | None = None) -> list[str]:
    """
    Return doc_ids visible to the caller: public docs (user_id IS NULL)
    plus the given user's own docs, if any.
    """
    session = get_session()
    try:
        query = session.query(Document.doc_id)
        if user_id is not None:
            query = query.filter(
                (Document.user_id == user_id) | (Document.user_id.is_(None))
            )
        else:
            query = query.filter(Document.user_id.is_(None))
        return [row[0] for row in query.all()]
    finally:
        session.close()


# ── Users ────────────────────────────────────────────────────────────────────

def get_user_by_id(user_id: str) -> Optional[dict]:
    session = get_session()
    try:
        user = session.get(User, user_id)
        if user is None:
            return None
        return {"id": user.id, "email": user.email}
    finally:
        session.close()


def get_user_by_email(email: str) -> Optional[dict]:
    session = get_session()
    try:
        user = session.query(User).filter(User.email == email).first()
        if user is None:
            return None
        return {"id": user.id, "email": user.email, "password_hash": user.password_hash}
    finally:
        session.close()


def create_user(email: str, password: str) -> dict:
    """Create a new user. Raises ValueError if email already exists."""
    session = get_session()
    try:
        existing = session.query(User).filter(User.email == email).first()
        if existing is not None:
            raise ValueError("Email already registered")

        user = User(email=email, password_hash=hash_password(password))
        session.add(user)
        session.commit()
        return {"id": user.id, "email": user.email}
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"create_user failed for {email}: {e}")
        session.rollback()
        raise
    finally:
        session.close()