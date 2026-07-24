"""
Document Intelligence + Agentic RAG - FastAPI Backend
======================================================
Security: CORS, rate limiting, MIME validation, hashed filenames.
Note: Auto-indexing disabled at startup to stay within Render free tier memory limits.
      Upload sample docs manually via the /upload page.
"""
import os
import sys
import logging

from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from models.db import init_db
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from limiter import limiter
from routers import upload, chat, documents, auth

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
app.include_router(auth.router, tags=["Auth"])


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


# --- Startup ---
@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up...")
    init_db()
    logger.info("Database tables ready.")
    logger.info("Startup complete — ready to serve requests.")