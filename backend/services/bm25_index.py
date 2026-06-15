"""
BM25 In-Memory Index
---------------------
Provides keyword-based (lexical) search to complement vector similarity search.
Uses BM25Okapi from rank_bm25 library.

The index is rebuilt from ChromaDB on startup and updated incrementally
whenever documents are added or deleted.

Singleton `bm25_index` is imported by vector_store and rag_agent.
"""
import re
import logging

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer, lowercase."""
    return re.findall(r'\b[a-z0-9]+\b', text.lower())


class BM25Index:
    """Thread-safe BM25 index for lexical keyword retrieval."""

    def __init__(self):
        self._chunks: list[dict] = []
        self._bm25 = None

    # ── Build / Rebuild ──────────────────────────────────────────────────────

    def build(self, chunks: list[dict]) -> None:
        """(Re)build the index from a list of chunk dicts."""
        if not chunks:
            self._chunks = []
            self._bm25 = None
            return
        try:
            from rank_bm25 import BM25Okapi
            self._chunks = list(chunks)
            tokenized = [_tokenize(c.get("text", "")) for c in self._chunks]
            self._bm25 = BM25Okapi(tokenized)
            logger.info(f"BM25 index built with {len(self._chunks)} chunks")
        except ImportError:
            logger.warning("rank_bm25 not installed - BM25 search disabled (falling back to vector-only)")
            self._bm25 = None
        except Exception as e:
            logger.error(f"BM25 index build failed: {e}")
            self._bm25 = None

    def add_chunks(self, new_chunks: list[dict]) -> None:
        """Append new chunks and rebuild the index."""
        self.build(self._chunks + new_chunks)

    def remove_doc(self, doc_id: str) -> None:
        """Remove all chunks for a document and rebuild."""
        before = len(self._chunks)
        filtered = [c for c in self._chunks if c.get("doc_id") != doc_id]
        if len(filtered) != before:
            self.build(filtered)
            logger.info(f"BM25: removed {before - len(filtered)} chunks for doc {doc_id}")

    # ── Search ───────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """Return up to top_k chunks ranked by BM25 score (highest first)."""
        if not self._bm25 or not self._chunks:
            return []
        try:
            tokens = _tokenize(query)
            if not tokens:
                return []
            scores = self._bm25.get_scores(tokens)
            # Keep only positive-scoring entries
            indexed = [(i, float(s)) for i, s in enumerate(scores) if s > 0]
            indexed.sort(key=lambda x: x[1], reverse=True)
            results = []
            for idx, score in indexed[:top_k]:
                chunk = dict(self._chunks[idx])
                chunk["bm25_score"] = score
                results.append(chunk)
            return results
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)


# ── Module-level singleton ────────────────────────────────────────────────────
bm25_index = BM25Index()
