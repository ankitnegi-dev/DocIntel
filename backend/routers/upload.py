"""
Upload Router
-------------
POST /upload   - Upload and process a single document
GET  /status/{doc_id} - Get processing status for a document
POST /bulk-upload - Upload multiple documents

File persistence model:
- Local UPLOADS_DIR / PAGES_DIR are working scratch space (parser needs local paths).
- After successful processing, the original file and all rendered page images
  are uploaded to object storage (Backblaze B2), then deleted from local disk.
- This keeps files durable across redeploys without requiring parser.py changes.

Auth model:
- Upload requires login. Uploaded documents are scoped to the uploading user
  via user_id on the Document row.
"""
import os
import hashlib
import logging
import asyncio
from pathlib import Path
from typing import Optional

try:
    import magic  # python-magic - true MIME detection from file bytes
except ImportError:  # pragma: no cover - optional dependency on Windows
    magic = None

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Request, Depends
from fastapi.responses import JSONResponse

from limiter import limiter
from models.document import DocumentResponse, ProcessingStatus
from services.document_repo import get_document, upsert_document, list_documents
from services import object_storage
from services.auth_deps import get_current_user_required

logger = logging.getLogger(__name__)
router = APIRouter()

STORAGE_DIR = Path(__file__).parent.parent / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
PAGES_DIR = STORAGE_DIR / "pages"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
PAGES_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)

# Security: allowed file types (extension + MIME)
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".png", ".jpg", ".jpeg"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "image/png",
    "image/jpeg",
    "image/jpg",
}
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "20")) * 1024 * 1024  # 20MB default

# Object storage key prefixes
ORIGINALS_PREFIX = "originals/"
PAGES_PREFIX = "pages/"

# In-memory processing status store
_processing_status: dict[str, ProcessingStatus] = {}


def _update_status(doc_id: str, status: str, progress: int, message: str, error: str = None):
    """Update the in-memory processing status for a document."""
    if doc_id in _processing_status:
        _processing_status[doc_id].status = status
        _processing_status[doc_id].progress = progress
        _processing_status[doc_id].message = message
        _processing_status[doc_id].error = error


def _scan_for_malicious_content(content: bytes) -> bool:
    """
    Basic malicious PDF scan: check for embedded JavaScript.
    Returns True if suspicious content found.
    """
    suspicious_markers = [b"/JS", b"/JavaScript", b"/Launch", b"/EmbeddedFile"]
    for marker in suspicious_markers:
        if marker in content:
            logger.warning(f"Suspicious PDF marker found: {marker}")
            return True
    return False


def _validate_file(file: UploadFile, content: bytes) -> None:
    """
    Validate file type, size, and basic content safety.
    Raises HTTPException on validation failure.
    """
    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )

    # Check extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Check MIME type from Content-Type header
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        # Be lenient with octet-stream (browsers sometimes send this)
        if content_type != "application/octet-stream":
            raise HTTPException(
                status_code=400,
                detail=f"Invalid content type: {content_type}"
            )

    # Deep MIME validation using python-magic when available; otherwise fall back
    # to extension/content-type checks so the app still runs on platforms without it.
    if magic is not None:
        detected_mime = magic.from_buffer(content[:2048], mime=True)
        if detected_mime not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"File content does not match allowed types. Detected: {detected_mime}"
            )

    # Basic PDF malicious content scan
    if ext == ".pdf":
        if _scan_for_malicious_content(content):
            logger.warning(f"Potentially malicious PDF uploaded: {file.filename}")
            # Log but don't block - warn only for accessibility


def _persist_to_object_storage(doc_id: str, file_path: Path, page_count: int) -> None:
    """
    Upload the original file and all rendered page images to object storage,
    then remove the local copies to free disk space.
    Best-effort: logs but does not raise on failure, since the document is
    already indexed and usable even if this durability step fails.
    """
    try:
        # Upload original file
        if file_path.exists():
            content = file_path.read_bytes()
            key = f"{ORIGINALS_PREFIX}{file_path.name}"
            object_storage.upload_bytes(key, content)
            file_path.unlink()
    except Exception as e:
        logger.warning(f"Failed to persist original file for {doc_id} to object storage: {e}")

    for page_num in range(1, page_count + 1):
        local_image = PAGES_DIR / f"{doc_id}_{page_num}.png"
        if not local_image.exists():
            continue
        try:
            content = local_image.read_bytes()
            key = f"{PAGES_PREFIX}{doc_id}_{page_num}.png"
            object_storage.upload_bytes(key, content, content_type="image/png")
            local_image.unlink()
        except Exception as e:
            logger.warning(f"Failed to persist page image {page_num} for {doc_id}: {e}")


async def _process_document(doc_id: str, file_path: Path, original_filename: str, user_id: Optional[str] = None):
    """
    Background task: parse -> classify -> index -> persist a document.
    Updates processing status throughout.
    """
    from services.parser import parse_document
    from services.classifier import classify_document
    from services.vector_store import index_document

    try:
        # --- PARSING ---
        _update_status(doc_id, "parsing", 20, "Parsing document...")
        pages = await asyncio.get_event_loop().run_in_executor(
            None, parse_document, str(file_path), doc_id
        )

        if not pages:
            raise ValueError("No content could be extracted from the document")

        # --- CLASSIFYING ---
        _update_status(doc_id, "classifying", 50, "Classifying document...")
        classification = await asyncio.get_event_loop().run_in_executor(
            None, classify_document, pages
        )

        # --- INDEXING ---
        _update_status(doc_id, "indexing", 75, "Indexing into vector store...")
        chunk_count = await asyncio.get_event_loop().run_in_executor(
            None, index_document, doc_id, original_filename, pages
        )

        final_status = "indexed" if chunk_count > 0 else "error"
        error_msg = None if chunk_count > 0 else "No extractable text found (scanned PDF without OCR support)"

        # --- PERSIST FILES TO OBJECT STORAGE ---
        if chunk_count > 0:
            _update_status(doc_id, "indexing", 90, "Persisting files to object storage...")
            await asyncio.get_event_loop().run_in_executor(
                None, _persist_to_object_storage, doc_id, file_path, len(pages)
            )

        # --- SAVE METADATA (Postgres) ---
        upsert_document(
            doc_id=doc_id,
            filename=original_filename,
            file_ext=Path(original_filename).suffix.lower(),
            file_size=file_path.stat().st_size if file_path.exists() else 0,
            status=final_status,
            page_count=len(pages),
            classification=classification,
            chunk_count=chunk_count,
            error_message=error_msg,
            user_id=user_id,
        )
        _update_status(
            doc_id,
            final_status,
            100 if chunk_count > 0 else 0,
            f"Indexed {chunk_count} chunks" if chunk_count > 0 else error_msg,
            error_msg,
        )

        if chunk_count > 0:
            logger.info(f"Successfully indexed: {original_filename} ({doc_id})")
        else:
            logger.warning(f"Indexed with 0 chunks: {original_filename} ({doc_id})")

    except Exception as e:
        logger.error(f"Processing failed for {doc_id}: {e}")
        _update_status(doc_id, "error", 0, "", str(e))

        # Save error metadata (Postgres)
        try:
            upsert_document(
                doc_id=doc_id,
                filename=original_filename,
                file_ext=Path(original_filename).suffix.lower(),
                file_size=file_path.stat().st_size if file_path.exists() else 0,
                status="error",
                error_message=str(e),
                user_id=user_id,
            )
        except Exception:
            pass


@router.post("/upload")
@limiter.limit("10/hour")
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user_required),
):
    """
    Upload a single document. Requires login. Returns immediately with doc_id
    and queued status. Processing happens in background. Poll /status/{doc_id}
    for updates.
    """
    content = await file.read()

    # Security validations
    _validate_file(file, content)

    # Compute SHA-256 hash for secure storage (prevents directory traversal)
    doc_hash = hashlib.sha256(content).hexdigest()
    ext = Path(file.filename or "file").suffix.lower()
    safe_filename = f"{doc_hash}{ext}"
    file_path = UPLOADS_DIR / safe_filename

    # Deduplicate: if already indexed, return existing
    existing = get_document(doc_hash)
    if existing and existing.get("status") == "indexed":
        return {
            "doc_id": doc_hash,
            "filename": existing["original_filename"],
            "page_count": existing["page_count"],
            "classification": existing.get("classification", {}),
            "status": "indexed",
            "message": "Document already indexed"
        }

    # Save file to local scratch disk (hashed filename - never original name)
    file_path.write_bytes(content)
    os.chmod(file_path, 0o600)  # Owner read/write only

    original_filename = file.filename or "unknown"
    user_id = current_user["id"]

    # Initialize processing status
    _processing_status[doc_hash] = ProcessingStatus(
        doc_id=doc_hash,
        filename=original_filename,
        status="queued",
        progress=0,
        message="Queued for processing"
    )

    # Process in background
    background_tasks.add_task(
        _process_document, doc_hash, file_path, original_filename, user_id
    )

    return {
        "doc_id": doc_hash,
        "filename": original_filename,
        "status": "queued",
        "message": "Document queued for processing"
    }


@router.get("/status/{doc_id}")
async def get_status(doc_id: str):
    """Get real-time processing status for a document."""
    # Check in-memory status first
    if doc_id in _processing_status:
        return _processing_status[doc_id]

    # Check persisted metadata (Postgres)
    meta = get_document(doc_id)
    if meta:
        return ProcessingStatus(
            doc_id=doc_id,
            filename=meta.get("original_filename", "unknown"),
            status=meta.get("status", "indexed"),
            progress=100 if meta.get("status") == "indexed" else 0,
            message=meta.get("error_message", "") or ""
        )

    raise HTTPException(status_code=404, detail="Document not found")


@router.post("/bulk-upload")
@limiter.limit("10/hour")
async def bulk_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user_required),
):
    """Upload multiple documents at once. Requires login."""
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 files per bulk upload")

    user_id = current_user["id"]
    results = []
    for file in files:
        content = await file.read()
        try:
            _validate_file(file, content)
        except HTTPException as e:
            results.append({
                "filename": file.filename,
                "status": "error",
                "error": e.detail
            })
            continue

        doc_hash = hashlib.sha256(content).hexdigest()
        ext = Path(file.filename or "file").suffix.lower()
        file_path = UPLOADS_DIR / f"{doc_hash}{ext}"
        file_path.write_bytes(content)
        os.chmod(file_path, 0o600)

        original_filename = file.filename or "unknown"

        _processing_status[doc_hash] = ProcessingStatus(
            doc_id=doc_hash,
            filename=original_filename,
            status="queued",
            progress=0,
            message="Queued for processing"
        )

        background_tasks.add_task(
            _process_document, doc_hash, file_path, original_filename, user_id
        )

        results.append({
            "doc_id": doc_hash,
            "filename": original_filename,
            "status": "queued"
        })

    return {"uploaded": len(results), "results": results}