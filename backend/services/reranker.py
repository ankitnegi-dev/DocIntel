"""
Cross-Encoder Re-Ranker
-----------------------
Re-ranks retrieved chunks using a cross-encoder model for better relevance.
Model: cross-encoder/ms-marco-MiniLM-L-6-v2 (22 MB, fast, MRC-tuned)
Lazy-loaded on first call; falls back to original order on any failure.
"""
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_model():
    """Load the cross-encoder model once and cache it."""
    from sentence_transformers import CrossEncoder
    model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512)
    logger.info("Cross-encoder reranker loaded: ms-marco-MiniLM-L-6-v2")
    return model


def rerank(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    """
    Re-rank chunks by cross-encoder relevance score.
    Returns top_k most relevant chunks in descending score order.
    Falls back to original order (truncated to top_k) on any error.
    """
    if not chunks:
        return chunks

    try:
        model = _get_model()
        # Pair query with each chunk's text (truncate to 512 tokens worth)
        pairs = [(query, c["text"][:600]) for c in chunks]
        scores = model.predict(pairs)

        ranked = sorted(
            zip(scores, chunks),
            key=lambda x: float(x[0]),
            reverse=True,
        )
        result = [c for _, c in ranked[:top_k]]
        logger.debug(f"Reranked {len(chunks)} → {len(result)} chunks. "
                     f"Top score: {float(ranked[0][0]):.3f}")
        return result

    except Exception as e:
        logger.warning(f"Reranking failed (using original order): {e}")
        return chunks[:top_k]
