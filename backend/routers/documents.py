"""
Documents Router
----------------
GET /documents              - List all indexed documents
GET /page-image              - Serve a rendered page PNG
GET /documents/{id}          - Get metadata for one document
DELETE /documents/{id}       - Remove a document
POST /documents/{id}/reindex - Re-process and re-index a document
"""
import logging
import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, Response

from services.document_repo import get_document, list_documents, upsert_document
from services import object_storage

logger = logging.getLogger(__name__)
router = APIRouter()

STORAGE_DIR = Path(__file__).parent.parent / "storage"
PAGES_DIR = STORAGE_DIR / "pages"
UPLOADS_DIR = STORAGE_DIR / "uploads"

ORIGINALS_PREFIX = "originals/"
PAGES_PREFIX = "pages/"


def _valid_doc_id(doc_id: str) -> bool:
    return len(doc_id) == 64 and all(c in "0123456789abcdef" for c in doc_id)


@router.get("/documents")
async def get_all_documents():
    """Return all indexed documents with their metadata and classifications."""
    docs = list_documents()
    return {
        "documents": docs,
        "total": len([d for d in docs if d.get("status") == "indexed"])
    }


@router.get("/documents/{doc_id}")
async def get_one_document(doc_id: str):
    """Get metadata for a specific document."""
    if not _valid_doc_id(doc_id):
        raise HTTPException(status_code=400, detail="Invalid document ID")

    doc = get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/page-image")
async def get_page_image(
    doc_id: str = Query(..., description="Document ID (SHA-256 hash)"),
    page: int = Query(..., ge=1, le=1000, description="Page number")
):
    """
    Serve a rendered page PNG.
    Images are ONLY served through this endpoint - never from direct disk path.
    Tries object storage (B2) first, falls back to local disk for any files
    that were processed before the object-storage migration.
    Validates doc_id to prevent path traversal.
    """
    if not _valid_doc_id(doc_id):
        raise HTTPException(status_code=400, detail="Invalid document ID")

    key = f"{PAGES_PREFIX}{doc_id}_{page}.png"

    # Try object storage first
    try:
        data = object_storage.download_bytes(key)
        if data:
            return Response(
                content=data,
                media_type="image/png",
                headers={
                    "Cache-Control": "private, max-age=3600",
                    "X-Content-Type-Options": "nosniff",
                }
            )
    except Exception as e:
        logger.warning(f"Object storage lookup failed for {key}: {e}")

    # Fallback: local disk (legacy files not yet migrated)
    image_path = PAGES_DIR / f"{doc_id}_{page}.png"
    try:
        resolved = image_path.resolve()
        if not str(resolved).startswith(str(PAGES_DIR.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Access denied")

    if not image_path.exists():
        raise HTTPException(status_code=404, detail=f"Page image not found: page {page}")

    return FileResponse(
        str(image_path),
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        }
    )


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Remove a document and all its associated data (vectors, Postgres row, files)."""
    if not _valid_doc_id(doc_id):
        raise HTTPException(status_code=400, detail="Invalid document ID")

    from services.vector_store import delete_document as vs_delete
    from models.db import get_session, Document

    # Remove from vector store
    vs_delete(doc_id)

    # Remove from Postgres
    session = get_session()
    try:
        doc = session.get(Document, doc_id)
        if doc:
            session.delete(doc)
            session.commit()
    finally:
        session.close()

    # Remove from object storage (pages + original)
    try:
        object_storage.delete_objects_with_prefix(f"{PAGES_PREFIX}{doc_id}_")
        object_storage.delete_objects_with_prefix(f"{ORIGINALS_PREFIX}{doc_id}")
    except Exception as e:
        logger.warning(f"Object storage cleanup failed for {doc_id}: {e}")

    # Remove any leftover local files (legacy/in-flight)
    for img_file in PAGES_DIR.glob(f"{doc_id}_*.png"):
        img_file.unlink()
    for up_file in UPLOADS_DIR.glob(f"{doc_id}.*"):
        up_file.unlink()

    return {"message": "Document deleted successfully", "doc_id": doc_id}


@router.post("/documents/{doc_id}/reindex")
async def reindex_document(doc_id: str, background_tasks: BackgroundTasks):
    """
    Re-process and re-index an existing document.
    Downloads the original file from object storage (or local disk fallback),
    deletes old vectors, and runs the full parse -> classify -> embed -> persist
    pipeline again in the background.
    """
    if not _valid_doc_id(doc_id):
        raise HTTPException(status_code=400, detail="Invalid document ID")

    meta = get_document(doc_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Document not found")

    original_filename = meta.get("original_filename", "unknown")
    file_ext = meta.get("file_ext") or Path(original_filename).suffix.lower() or ".pdf"

    # Locate the original file: object storage first, then local disk fallback
    file_path = UPLOADS_DIR / f"{doc_id}{file_ext}"
    found = False

    if not file_path.exists():
        key = f"{ORIGINALS_PREFIX}{doc_id}{file_ext}"
        try:
            data = object_storage.download_bytes(key)
            if data:
                UPLOADS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
                file_path.write_bytes(data)
                found = True
        except Exception as e:
            logger.warning(f"Could not fetch original from object storage for reindex: {e}")
    else:
        found = True

    if not found:
        raise HTTPException(
            status_code=404,
            detail="Original file not found in object storage or on disk. Cannot reindex."
        )

    async def _do_reindex():
        from services.parser import parse_document
        from services.classifier import classify_document
        from services.vector_store import index_document, delete_document as vs_delete
        from routers.upload import _persist_to_object_storage

        try:
            vs_delete(doc_id)

            pages = await asyncio.get_event_loop().run_in_executor(
                None, parse_document, str(file_path), doc_id
            )
            if not pages:
                raise ValueError("No content extracted")

            classification = await asyncio.get_event_loop().run_in_executor(
                None, classify_document, pages
            )

            chunk_count = await asyncio.get_event_loop().run_in_executor(
                None, index_document, doc_id, original_filename, pages
            )

            final_status = "indexed" if chunk_count > 0 else "error"
            error_msg = None if chunk_count > 0 else "No extractable text found"

            if chunk_count > 0:
                await asyncio.get_event_loop().run_in_executor(
                    None, _persist_to_object_storage, doc_id, file_path, len(pages)
                )

            upsert_document(
                doc_id=doc_id,
                filename=original_filename,
                file_ext=file_ext,
                file_size=file_path.stat().st_size if file_path.exists() else 0,
                status=final_status,
                page_count=len(pages),
                classification=classification,
                chunk_count=chunk_count,
                error_message=error_msg,
            )
            logger.info(f"Reindex complete: {original_filename} ({chunk_count} chunks)")

        except Exception as e:
            logger.error(f"Reindex failed for {doc_id}: {e}")
            upsert_document(
                doc_id=doc_id,
                filename=original_filename,
                file_ext=file_ext,
                file_size=file_path.stat().st_size if file_path.exists() else 0,
                status="error",
                error_message=str(e),
            )

    background_tasks.add_task(_do_reindex)

    return {
        "message": "Reindexing started",
        "doc_id": doc_id,
        "filename": original_filename,
    }