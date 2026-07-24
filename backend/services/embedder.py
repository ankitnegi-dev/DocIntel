"""
Embedder Service
----------------
Uses ChromaDB's built-in ONNXRuntime embedding function.
No torch required - stays within Render free tier memory limits.
"""
import logging

logger = logging.getLogger(__name__)

_ef = None

def _get_ef():
    global _ef
    if _ef is None:
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
        logger.info("Loading ONNX embedding function...")
        _ef = ONNXMiniLM_L6_V2()
        logger.info("ONNX embedding function ready")
    return _ef

def embed_chunks(chunks: list[str]) -> list[list[float]]:
    if not chunks:
        return []
    try:
        ef = _get_ef()
        embeddings = ef(chunks)
        return [[float(x) for x in e] for e in embeddings]
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise

def embed_query(query: str) -> list[float]:
    results = embed_chunks([query])
    return results[0] if results else []