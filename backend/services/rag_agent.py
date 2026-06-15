"""
Agentic RAG Service
--------------------
Retrieval-Augmented Generation agent with:
- Cross-encoder re-ranking for better retrieval quality
- Multi-document comparison mode (auto-detected from query)
- Streaming SSE via generator
- Inline [Doc, Page N] citations with source chunk text
- 3 follow-up question suggestions per answer

Design principles:
- ONLY answers from retrieved evidence — never hallucinate
- Returns "no information found" if similarity threshold not met
- Citations include doc_name, page_num, image_path, excerpt, chunk_text
- Answers formatted in markdown (bullets, bold, headers, tables) for readability
"""
import re
import os
import json
import logging
from pathlib import Path
from typing import Generator

from groq import Groq

from models.chat import ChatMessage, Citation, ChatResponse
from services import vector_store
from services.reranker import rerank
from services.bm25_index import bm25_index

logger = logging.getLogger(__name__)

PAGES_DIR = Path(__file__).parent.parent / "storage" / "pages"

# Relevance threshold — cosine distance (lower = more similar)
RELEVANCE_THRESHOLD = 1.2

# Groq models
RAG_MODEL       = "llama-3.3-70b-versatile"   # Main Q&A — best quality
FOLLOWUP_MODEL  = "llama-3.1-8b-instant"       # Follow-up suggestions — fast

NO_INFO_RESPONSE = (
    "I could not find relevant information in the uploaded documents "
    "to answer your question. Please upload relevant documents or rephrase your query."
)

# Keywords that trigger multi-document comparison mode
COMPARISON_KEYWORDS = [
    "compare", "comparison", "versus", " vs ", "difference between",
    "differences", "contrast", "which is better", "side by side",
    "how do they differ", "what's the difference", "similarities",
]


def _get_client() -> Groq:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError("GROQ_API_KEY not configured")
    return Groq(api_key=key)


def _is_comparison_query(query: str) -> bool:
    q = query.lower()
    return any(kw in q for kw in COMPARISON_KEYWORDS)


def _get_page_image_path(doc_id: str, page_num: int) -> str:
    image_path = PAGES_DIR / f"{doc_id}_{page_num}.png"
    return str(image_path) if image_path.exists() else ""


def build_rag_prompt(query: str, chunks: list[dict], history: list[ChatMessage],
                     comparison_mode: bool = False) -> str:
    """Construct the RAG synthesis prompt with formatting instructions."""
    context_lines = []
    for i, chunk in enumerate(chunks, 1):
        doc_name = chunk["doc_name"]
        page_num = chunk["page_num"]
        text = chunk["text"][:800]
        context_lines.append(f"[Chunk {i} — from: {doc_name}, page {page_num}]\n{text}")

    context_text = "\n\n".join(context_lines)

    history_text = ""
    if history:
        recent = history[-6:]
        history_lines = []
        for msg in recent:
            role = "User" if msg.role == "user" else "Assistant"
            history_lines.append(f"{role}: {msg.content[:300]}")
        history_text = "\n".join(history_lines)

    comparison_instructions = ""
    if comparison_mode:
        comparison_instructions = """
COMPARISON MODE — the user wants a side-by-side comparison:
- Use a markdown table if comparing 2-3 items on multiple dimensions
- Or use ## Document A / ## Document B headers with parallel bullet points
- Explicitly name each document being compared
- Highlight key differences in **bold**
- End with a brief ## Summary section
"""

    prompt = f"""You are a document intelligence assistant. Answer the user's question using ONLY the document excerpts provided below.

FORMATTING RULES (always follow these):
- Start with a **1-sentence direct answer** in bold if the answer is a specific fact
- Use bullet points (- item) for any list of 3 or more items
- Use **bold** for key terms, numbers, names, dates, amounts
- Use ## headers when covering multiple distinct sub-topics
- Keep paragraphs short — 2-3 sentences max
- If comparing items, use a table or side-by-side ## sections
{comparison_instructions}
STRICT RULES:
1. Cite sources inline as [DocName, Page N] — use exact document filename and page number.
2. If the answer is not in the excerpts, respond with exactly: "I could not find relevant information in the uploaded documents."
3. NEVER use knowledge outside the provided excerpts.
4. NEVER invent citations.

CONTEXT:
{context_text}

{'CONVERSATION HISTORY:' + chr(10) + history_text if history_text else ''}

USER QUESTION: {query}

Answer (use markdown formatting + inline citations [DocName, Page N]):"""

    return prompt


def build_followup_prompt(query: str, answer: str) -> str:
    """Generate a prompt to produce 3 follow-up question suggestions."""
    return f"""Based on this Q&A exchange about a document, suggest exactly 3 short, specific follow-up questions.

Original question: {query}
Answer summary: {answer[:400]}

Rules:
- Each question must be answerable from typical business/finance/legal/research documents
- Keep each question under 12 words
- Make them progressively deeper or related to different aspects
- Return ONLY a JSON array of 3 strings, no other text

Example format: ["Question 1?", "Question 2?", "Question 3?"]

JSON array:"""


def extract_citations(answer_text: str, retrieved_chunks: list[dict]) -> list[Citation]:
    """Parse [Doc Name, Page N] markers and map to chunk metadata."""
    pattern = r'\[([^\]]+?),\s*[Pp]age\s+(\d+)\]'
    matches = re.findall(pattern, answer_text)

    seen = set()
    citations = []

    for doc_name_raw, page_num_str in matches:
        doc_name = doc_name_raw.strip()
        page_num = int(page_num_str)
        key = (doc_name.lower(), page_num)

        if key in seen:
            continue
        seen.add(key)

        matching_chunk = None
        for chunk in retrieved_chunks:
            chunk_doc = chunk["doc_name"].lower()
            if (doc_name.lower() in chunk_doc or chunk_doc in doc_name.lower()
                    or _similar_names(doc_name, chunk["doc_name"])):
                if chunk["page_num"] == page_num:
                    matching_chunk = chunk
                    break

        if matching_chunk is None:
            for chunk in retrieved_chunks:
                if chunk["page_num"] == page_num:
                    matching_chunk = chunk
                    break

        if matching_chunk:
            doc_id = matching_chunk["doc_id"]
            image_path = _get_page_image_path(doc_id, page_num)
            chunk_text = matching_chunk["text"]
            excerpt = (chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text)

            citations.append(Citation(
                doc_name=matching_chunk["doc_name"],
                doc_id=doc_id,
                page_num=page_num,
                image_path=image_path,
                excerpt=excerpt,
                chunk_text=chunk_text,
            ))

    return citations


def _similar_names(name1: str, name2: str) -> bool:
    n1 = re.sub(r'[^a-z0-9]', '', name1.lower())
    n2 = re.sub(r'[^a-z0-9]', '', name2.lower())
    return n1 == n2 or n1 in n2 or n2 in n1


def _generate_follow_ups(query: str, answer: str) -> list[str]:
    """Call Groq to get 3 follow-up question suggestions. Returns [] on failure."""
    try:
        client = _get_client()
        completion = client.chat.completions.create(
            model=FOLLOWUP_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": build_followup_prompt(query, answer)}]
        )
        raw = completion.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        suggestions = json.loads(raw)
        if isinstance(suggestions, list):
            return [str(q) for q in suggestions[:3]]
    except Exception as e:
        logger.debug(f"Follow-up generation failed: {e}")
    return []


def _chunk_key(chunk: dict) -> str:
    """Unique key for deduplication across vector + BM25 results."""
    return f"{chunk.get('doc_id', '')}_{chunk.get('page_num', 0)}_{chunk.get('text', '')[:60]}"


def _hybrid_search(query: str, n_fetch: int) -> list[dict]:
    """
    Combine vector similarity search and BM25 keyword search via
    Reciprocal Rank Fusion (RRF, k=60). Deduplicates by chunk key.
    Falls back to vector-only if BM25 index is empty.
    """
    vector_results = vector_store.search(query, n_results=n_fetch)
    bm25_results   = bm25_index.search(query, top_k=n_fetch)

    if not bm25_results:
        return vector_results  # BM25 not populated yet

    k = 60  # Standard RRF constant
    rrf_scores: dict[str, float] = {}
    chunk_map:  dict[str, dict]  = {}

    # Score vector results (rank ascending by distance = best first)
    for rank, chunk in enumerate(vector_results):
        key = _chunk_key(chunk)
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        chunk_map[key] = chunk

    # Score BM25 results (already sorted best-first by score)
    for rank, chunk in enumerate(bm25_results):
        key = _chunk_key(chunk)
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        if key not in chunk_map:
            chunk["distance"] = 0.5
            chunk_map[key] = chunk

    ranked_keys = sorted(rrf_scores, key=lambda k_: rrf_scores[k_], reverse=True)
    merged = [chunk_map[k_] for k_ in ranked_keys[:n_fetch]]
    logger.debug(f"Hybrid search: {len(vector_results)} vector + {len(bm25_results)} BM25 → {len(merged)} merged")
    return merged


def _retrieve_and_rerank(query: str, comparison_mode: bool) -> list[dict]:
    """Hybrid retrieve (vector + BM25 via RRF) then cross-encoder re-rank."""
    n_fetch = 12 if comparison_mode else 8
    chunks = _hybrid_search(query, n_fetch)
    relevant = [c for c in chunks if c.get("distance", 0) < RELEVANCE_THRESHOLD]
    if not relevant:
        return []
    top_k = 6 if comparison_mode else 5
    return rerank(query, relevant, top_k=top_k)


def stream_answer(query: str, history: list[ChatMessage]) -> Generator[str, None, None]:
    """
    Generator yielding SSE-formatted data strings.
    Events:
      {"type":"text","delta":"..."}
      {"type":"done","citations":[...],"follow_ups":[...],"sources_found":bool,"comparison_mode":bool}
      {"type":"error","message":"..."}
    """
    query = query[:1000].strip()
    comparison_mode = _is_comparison_query(query)
    if comparison_mode:
        logger.info(f"Comparison mode: {query[:60]}")

    relevant_chunks = _retrieve_and_rerank(query, comparison_mode)

    if not relevant_chunks:
        logger.info(f"No relevant chunks for: {query[:50]}")
        yield f"data: {json.dumps({'type': 'text', 'delta': NO_INFO_RESPONSE})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'citations': [], 'follow_ups': [], 'sources_found': False, 'comparison_mode': False})}\n\n"
        return

    try:
        client = _get_client()
        prompt = build_rag_prompt(query, relevant_chunks, history, comparison_mode)
        full_text = ""

        # Groq streaming
        stream = client.chat.completions.create(
            model=RAG_MODEL,
            max_tokens=1500 if comparison_mode else 1024,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full_text += delta
                yield f"data: {json.dumps({'type': 'text', 'delta': delta})}\n\n"

        if "could not find relevant information" in full_text.lower():
            yield f"data: {json.dumps({'type': 'done', 'citations': [], 'follow_ups': [], 'sources_found': False, 'comparison_mode': comparison_mode})}\n\n"
            return

        citations = extract_citations(full_text, relevant_chunks)
        follow_ups = _generate_follow_ups(query, full_text)

        yield f"data: {json.dumps({'type': 'done', 'citations': [c.model_dump() for c in citations], 'follow_ups': follow_ups, 'sources_found': True, 'comparison_mode': comparison_mode})}\n\n"

    except Exception as e:
        logger.error(f"Streaming RAG failed: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': 'Unable to process query. Please ensure GROQ_API_KEY is configured.'})}\n\n"


def answer_query(query: str, history: list[ChatMessage]) -> ChatResponse:
    """Non-streaming RAG (kept for /chat compatibility)."""
    query = query[:1000].strip()
    comparison_mode = _is_comparison_query(query)
    relevant_chunks = _retrieve_and_rerank(query, comparison_mode)

    if not relevant_chunks:
        return ChatResponse(answer=NO_INFO_RESPONSE, citations=[], sources_found=False)

    try:
        client = _get_client()
        prompt = build_rag_prompt(query, relevant_chunks, history, comparison_mode)
        completion = client.chat.completions.create(
            model=RAG_MODEL,
            max_tokens=1500 if comparison_mode else 1024,
            messages=[{"role": "user", "content": prompt}]
        )
        answer_text = completion.choices[0].message.content.strip()

        if "could not find relevant information" in answer_text.lower():
            return ChatResponse(answer=NO_INFO_RESPONSE, citations=[], sources_found=False)

        citations = extract_citations(answer_text, relevant_chunks)
        return ChatResponse(answer=answer_text, citations=citations, sources_found=True)

    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        return ChatResponse(
            answer="Unable to process query at this time.",
            citations=[],
            sources_found=False,
        )