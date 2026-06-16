"""
Document Intelligence + Agentic RAG — FastAPI Backend
======================================================
Startup: auto-indexes sample_docs/ if not already indexed.
Security: CORS, rate limiting, MIME validation, hashed filenames.
"""
import os
import sys
import logging
import asyncio
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from limiter import limiter
from routers import upload, chat, documents

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Document Intelligence + Agentic RAG",
    description="AI-powered document parsing, classification, and RAG chatbot.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Attach rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
frontend_url = os.getenv("FRONTEND_URL", "")
if frontend_url:
    allowed_origins.append(frontend_url)
allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# --- Security headers middleware ---
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "ALLOWALL"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# --- Include routers ---
app.include_router(upload.router, tags=["Upload"])
app.include_router(chat.router, tags=["Chat"])
app.include_router(documents.router, tags=["Documents"])


# --- Health check ---
@app.get("/health")
async def health():
    from services.vector_store import get_document_count
    doc_count = get_document_count()
    return {
        "status": "healthy",
        "indexed_chunks": doc_count,
        "api_configured": bool(os.getenv("GROQ_API_KEY"))
    }


# --- Startup: auto-index sample documents only ---
@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up...")

    await _auto_index_samples()

    # Build BM25 index from existing ChromaDB data
    try:
        from services.vector_store import get_all_chunks
        from services.bm25_index import bm25_index
        chunks = get_all_chunks()
        if chunks:
            bm25_index.build(chunks)
            logger.info(f"BM25 index warmed up with {len(chunks)} chunks")
    except Exception as e:
        logger.warning(f"BM25 warmup failed (non-fatal): {e}")


async def _auto_index_samples():
    """Index sample_docs/ directory if documents haven't been indexed yet."""
    sample_dir = Path(__file__).parent / "sample_docs"
    if not sample_dir.exists():
        logger.info("No sample_docs directory found, skipping auto-indexing")
        return

    metadata_dir = Path(__file__).parent / "storage" / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    from routers.upload import _process_document, UPLOADS_DIR
    import hashlib

    for sample_file in sample_dir.iterdir():
        if sample_file.suffix.lower() not in {".pdf", ".txt"}:
            continue

        try:
            content = sample_file.read_bytes()
            doc_hash = hashlib.sha256(content).hexdigest()
            meta_path = metadata_dir / f"{doc_hash}.json"

            if meta_path.exists():
                import json
                existing = json.loads(meta_path.read_text())
                if existing.get("status") == "indexed":
                    logger.info(f"Sample already indexed: {sample_file.name}")
                    continue

            ext = sample_file.suffix.lower()
            dest_path = UPLOADS_DIR / f"{doc_hash}{ext}"
            dest_path.write_bytes(content)

            logger.info(f"Auto-indexing sample: {sample_file.name}")
            await _process_document(doc_hash, dest_path, sample_file.name)

        except Exception as e:
            logger.error(f"Failed to auto-index {sample_file.name}: {e}")