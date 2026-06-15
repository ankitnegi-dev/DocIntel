"""Pydantic models for chat messages and RAG responses."""
from pydantic import BaseModel, Field
from typing import Optional


class ChatMessage(BaseModel):
    """A single message in the conversation."""
    role: str      # 'user' | 'assistant'
    content: str


class Citation(BaseModel):
    """A citation returned with an answer."""
    doc_name: str
    doc_id: str
    page_num: int
    image_path: str
    excerpt: str
    chunk_text: str = ""  # Full source chunk text for transparency


class ChatRequest(BaseModel):
    """Request body for POST /chat."""
    query: str = Field(..., max_length=1000, description="User question")
    history: list[ChatMessage] = Field(default=[], max_length=10)


class ChatResponse(BaseModel):
    """Response from the RAG agent."""
    answer: str
    citations: list[Citation] = []
    sources_found: bool = True
