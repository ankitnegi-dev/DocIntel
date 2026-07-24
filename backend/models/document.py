"""
Document Models
----------------
Pydantic models for document parsing, metadata, and API responses.
"""
from typing import Optional
from pydantic import BaseModel


class PageData(BaseModel):
    """Structured output from the parser for a single page."""
    page_num: int
    text: str
    tables: list[str] = []
    image_path: str = ""
    extraction_method: str = "text"   # 'text' | 'ocr' | 'pdfplumber'
    word_count: int = 0
    has_tables: bool = False
    ocr_confidence: float = 1.0


class DocumentMetadata(BaseModel):
    """Legacy JSON-metadata shape, still used by create_samples.py."""
    doc_id: str
    original_filename: str
    upload_time: str
    page_count: int = 0
    file_size: int = 0
    classification: Optional[dict] = None
    status: str = "queued"
    error_message: Optional[str] = None


class DocumentResponse(BaseModel):
    """Response shape for document metadata endpoints."""
    doc_id: str
    original_filename: str
    page_count: int = 0
    file_size: int = 0
    classification: Optional[dict] = None
    status: str = "queued"


class ProcessingStatus(BaseModel):
    """Live processing status for /status/{doc_id}."""
    doc_id: str
    filename: str
    status: str = "queued"
    progress: int = 0
    message: str = ""
    error: Optional[str] = None