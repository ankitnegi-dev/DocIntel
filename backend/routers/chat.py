"""
Chat Router
-----------
POST /chat        - Agentic RAG query (non-streaming, JSON response)
POST /chat/stream - Streaming SSE variant: yields text deltas + done event

Auth model:
- Chat works for both anonymous and logged-in users (demo mode preserved).
- If logged in, retrieval is scoped to the user's own documents plus public/demo
  documents. If anonymous, retrieval is scoped to public/demo documents only.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse

from limiter import limiter
from models.chat import ChatRequest, ChatResponse
from services.rag_agent import answer_query, stream_answer
from services.auth_deps import get_current_user_optional

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("60/hour")
async def chat(
    request: Request,
    body: ChatRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Process a chat query using the Agentic RAG pipeline.
    Returns answer with inline citations and page image paths.
    """
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    user_id = current_user["id"] if current_user else None

    try:
        response = answer_query(query, body.history, user_id=user_id)
        return response
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail="An error occurred processing your query")


@router.post("/chat/stream")
@limiter.limit("60/hour")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Streaming SSE chat endpoint.
    Yields:
      data: {"type":"text","delta":"..."}
      data: {"type":"done","citations":[...],"follow_ups":[...],"sources_found":bool}
      data: {"type":"error","message":"..."}
    """
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    user_id = current_user["id"] if current_user else None

    return StreamingResponse(
        stream_answer(query, body.history, user_id=user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )