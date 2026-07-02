"""
Upload Router
-------------
POST /upload   - Upload and process a single document
GET  /status/{doc_id} - Get processing status for a document
POST /bulk-upload - Upload multiple documents

Processing model:
- Uploads are enqueued as arq jobs (Redis-backed), processed by a separate
  worker process (see worker.py / tasks.py). This means an in-flight upload
  survives an API server restart/redeploy -- the job stays in Redis until a
  worker picks it up, unlike the old FastAPI BackgroundTasks approach where
  an in-process restart would silently lose the job.
- Status is read directly from Postgres (the source of truth). Note: since
  processing now runs in a separate worker process, fine-grained live
  progress (parsing/classifying/indexing percentages) is no longer tracked --
  status shows queued -> indexed/error. This is a deliberate trade-off of
  durability over granular live progress.

File persistence model:
- Local UPLOADS_DIR / PAGES_DIR are working scratch space (parser needs local paths).
- After successful processing, the original file and all rendered page images
  are uploaded to object storage (Backblaze B2), then deleted from local disk.

Auth model:
- Upload requires login. Uploaded documents are scoped to the uploading user
  via user_id on the Document row.
"""
import os
import hashlib
import logging
from pathlib import Path
from typing import Optional

try:
    import magic  # python-magic - true MIME detection from file bytes
except ImportError:  # pragma: no cover - optional dependency on Windows
    magic = None

from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Depends
from fastapi.responses import JSONResponse

from limiter import limiter
from models.document import DocumentResponse, ProcessingStatus
from services.document_repo import get_document, upsert_document, list_documents
from services.job_queue import enqueue_process_document
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
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        if content_type != "application/octet-stream":
            raise HTTPException(
                status_code=400,
                detail=f"Invalid content type: {content_type}"
            )

    if magic is not None:
        detected_mime = magic.from_buffer(content[:2048], mime=True)
        if detected_mime not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"File content does not match allowed types. Detected: {detected_mime}"
            )

    if ext == ".pdf":
        if _scan_for_malicious_content(content):
            logger.warning(f"Potentially malicious PDF uploaded: {file.filename}")


@router.post("/upload")
@limiter.limit("10/hour")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user_required),
):
    """
    Upload a single document. Requires login. Returns immediately with doc_id
    and queued status. Processing happens via the arq job queue (Redis-backed,
    survives API restarts). Poll /status/{doc_id} for updates.
    """
    content = await file.read()

    _validate_file(file, content)

    doc_hash = hashlib.sha256(content).hexdigest()
    ext = Path(file.filename or "file").suffix.lower()
    safe_filename = f"{doc_hash}{ext}"
    file_path = UPLOADS_DIR / safe_filename

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

    file_path.write_bytes(content)
    os.chmod(file_path, 0o600)

    original_filename = file.filename or "unknown"
    user_id = current_user["id"]

    # Create a "queued" row immediately so /status has something to read
    upsert_document(
        doc_id=doc_hash,
        filename=original_filename,
        file_ext=ext,
        file_size=file_path.stat().st_size,
        status="queued",
        user_id=user_id,
    )

    await enqueue_process_document(
        doc_id=doc_hash,
        file_path=str(file_path),
        original_filename=original_filename,
        user_id=user_id,
    )

    return {
        "doc_id": doc_hash,
        "filename": original_filename,
        "status": "queued",
        "message": "Document queued for processing"
    }


@router.get("/status/{doc_id}")
async def get_status(doc_id: str):
    """
    Get processing status for a document, read from Postgres (the source of
    truth). Note: since processing now runs in a separate worker process,
    granular in-flight stages (parsing/classifying/indexing) are not tracked
    live -- status shows queued -> indexed/error.
    """
    meta = get_document(doc_id)
    if meta:
        status = meta.get("status", "queued")
        return ProcessingStatus(
            doc_id=doc_id,
            filename=meta.get("original_filename", "unknown"),
            status=status,
            progress=100 if status == "indexed" else (0 if status == "error" else 50),
            message=meta.get("error_message", "") or ""
        )

    raise HTTPException(status_code=404, detail="Document not found")


@router.post("/bulk-upload")
@limiter.limit("10/hour")
async def bulk_upload(
    request: Request,
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

        upsert_document(
            doc_id=doc_hash,
            filename=original_filename,
            file_ext=ext,
            file_size=file_path.stat().st_size,
            status="queued",
            user_id=user_id,
        )

        await enqueue_process_document(
            doc_id=doc_hash,
            file_path=str(file_path),
            original_filename=original_filename,
            user_id=user_id,
        )

        results.append({
            "doc_id": doc_hash,
            "filename": original_filename,
            "status": "queued"
        })

    return {"uploaded": len(results), "results": results}