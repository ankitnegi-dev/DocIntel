"""Pydantic models for document data structures."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PageData(BaseModel):
    """Represents a single parsed page from a document."""
    page_num: int
    text: str
    tables: list[str]          # Markdown-formatted tables
    image_path: str            # Path to rendered PNG
    extraction_method: str     # 'pdfplumber', 'ocr', or 'text'
    word_count: int
    has_tables: bool = False
    ocr_confidence: float = 1.0


class DocumentMetadata(BaseModel):
    """Stored metadata for an indexed document."""
    doc_id: str                # SHA-256 hash of file content
    original_filename: str
    upload_time: str
    page_count: int
    file_size: int
    classification: Optional[dict] = None
    status: str = "indexed"    # queued | parsing | classifying | indexed | error
    error_message: Optional[str] = None


class DocumentResponse(BaseModel):
    """Response model after successful upload."""
    doc_id: str
    filename: str
    page_count: int
    classification: dict
    status: str = "indexed"


class ProcessingStatus(BaseModel):
    """Real-time processing status for a document."""
    doc_id: str
    filename: str
    status: str                # queued | parsing | classifying | indexing | indexed | error
    progress: int = 0          # 0-100
    message: str = ""
    error: Optional[str] = None
