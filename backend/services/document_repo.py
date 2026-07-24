"""
Document Repository
--------------------
Postgres-backed replacement for the old storage/metadata/*.json files.

Access model:
- Document.user_id records who originally uploaded/created the content (informational).
- DocumentAccess is the actual permission table: a row means that user can see/query
  that document. Public/demo documents (Document.user_id IS NULL) are visible to
  everyone regardless of DocumentAccess rows.
- This separation exists so that identical content uploaded by different users can
  share the same underlying Chroma vectors / B2 files (deduped by content hash)
  while each user still gets their own private, listable, deletable entry.
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.exc import IntegrityError

from models.db import get_session, Document, User, DocumentAccess
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
    """
    Insert or update a document's content/status record. user_id=None means a
    public/demo document. On first creation with a user_id, that user is also
    granted access (see DocumentAccess). Re-uploads of already-existing content
    by a *different* user should call grant_document_access() separately
    (see upload.py's dedup path) rather than relying on this function to do it.
    """
    session = get_session()
    try:
        doc = session.get(Document, doc_id)
        is_new = doc is None
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

        if is_new and user_id is not None:
            session.add(DocumentAccess(doc_id=doc_id, user_id=user_id))

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
    If user_id is given: returns public documents PLUS documents that user has
    been granted access to (whether they uploaded the original or a deduped
    re-upload of identical content).
    If user_id is None: returns only public documents (anonymous/demo view).
    """
    session = get_session()
    try:
        if user_id is not None:
            accessible_ids = session.query(DocumentAccess.doc_id).filter(
                DocumentAccess.user_id == user_id
            ).subquery()
            query = session.query(Document).filter(
                (Document.user_id.is_(None)) | (Document.doc_id.in_(accessible_ids))
            )
        else:
            query = session.query(Document).filter(Document.user_id.is_(None))

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
    plus docs the given user has been granted access to.
    """
    session = get_session()
    try:
        if user_id is not None:
            accessible_ids = session.query(DocumentAccess.doc_id).filter(
                DocumentAccess.user_id == user_id
            ).subquery()
            query = session.query(Document.doc_id).filter(
                (Document.user_id.is_(None)) | (Document.doc_id.in_(accessible_ids))
            )
        else:
            query = session.query(Document.doc_id).filter(Document.user_id.is_(None))
        return [row[0] for row in query.all()]
    finally:
        session.close()


def user_has_access(doc_id: str, user_id: str) -> bool:
    """True if the document is public, or the user has an explicit access grant."""
    session = get_session()
    try:
        doc = session.get(Document, doc_id)
        if doc is None:
            return False
        if doc.user_id is None:
            return True
        access = session.query(DocumentAccess).filter(
            DocumentAccess.doc_id == doc_id, DocumentAccess.user_id == user_id
        ).first()
        return access is not None
    finally:
        session.close()


def grant_document_access(doc_id: str, user_id: str) -> None:
    """
    Grant a user access to an already-indexed document (used on dedup: identical
    content already exists, so no reprocessing happens, but the new uploader
    still gets their own visible/deletable entry). Idempotent.
    """
    session = get_session()
    try:
        existing = session.query(DocumentAccess).filter(
            DocumentAccess.doc_id == doc_id, DocumentAccess.user_id == user_id
        ).first()
        if existing is not None:
            return
        session.add(DocumentAccess(doc_id=doc_id, user_id=user_id))
        session.commit()
    except IntegrityError:
        # Race: another request granted it concurrently -- fine, already exists.
        session.rollback()
    except Exception as e:
        logger.error(f"grant_document_access failed for {doc_id}/{user_id}: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def revoke_document_access(doc_id: str, user_id: str) -> int:
    """
    Revoke a user's access to a document. Returns the number of remaining
    access holders after revocation, so the caller can decide whether the
    underlying content (Chroma vectors, B2 files, Postgres row) should be
    fully purged (0 remaining) or left in place for other users.
    """
    session = get_session()
    try:
        access = session.query(DocumentAccess).filter(
            DocumentAccess.doc_id == doc_id, DocumentAccess.user_id == user_id
        ).first()
        if access is not None:
            session.delete(access)
            session.commit()

        remaining = session.query(DocumentAccess).filter(
            DocumentAccess.doc_id == doc_id
        ).count()
        return remaining
    except Exception as e:
        logger.error(f"revoke_document_access failed for {doc_id}/{user_id}: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def delete_document_row(doc_id: str) -> None:
    """Delete the Document row itself (and its access rows via cascade at the DB
    level if configured, or explicitly here). Call only when no access holders
    remain and the document isn't public."""
    session = get_session()
    try:
        session.query(DocumentAccess).filter(DocumentAccess.doc_id == doc_id).delete()
        doc = session.get(Document, doc_id)
        if doc:
            session.delete(doc)
        session.commit()
    except Exception as e:
        logger.error(f"delete_document_row failed for {doc_id}: {e}")
        session.rollback()
        raise
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