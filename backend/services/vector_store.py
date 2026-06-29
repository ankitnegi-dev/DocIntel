"""
Vector Store Service
---------------------
Manages ChromaDB for document chunk storage and similarity search.
Uses upsert() for idempotent indexing (safe to re-index).
"""
import logging
import os
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

from models.document import PageData
from services import embedder
from services.bm25_index import bm25_index

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).parent.parent / "storage"
CHROMA_PATH = STORAGE_DIR / "chroma_db"
CHROMA_PATH.mkdir(parents=True, exist_ok=True, mode=0o700)

# Chunking constants
MAX_WORDS_PER_CHUNK = 400
CHUNK_OVERLAP_WORDS = 50
MIN_CHUNK_WORDS = 10

# ChromaDB client (lazy init)
_client = None
_collection = None


def _get_collection():
    """Get or create the ChromaDB collection (Cloud if configured, else local)."""
    global _client, _collection
    if _collection is None:
        api_key  = os.getenv("CHROMA_API_KEY")
        tenant   = os.getenv("CHROMA_TENANT")
        database = os.getenv("CHROMA_DATABASE")

        if api_key and tenant and database:
            _client = chromadb.CloudClient(
                api_key=api_key,
                tenant=tenant,
                database=database,
            )
            logger.info("Connected to Chroma Cloud")
        else:
            _client = chromadb.PersistentClient(
                path=str(CHROMA_PATH),
                settings=Settings(anonymized_telemetry=False)
            )
            logger.info("Using local ChromaDB")

        _collection = _client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"ChromaDB collection ready. Items: {_collection.count()}")
    return _collection


def _chunk_text(text: str, page_num: int, doc_id: str,
                doc_name: str, extraction_method: str) -> list[dict]:
    """
    Split page text into overlapping chunks.
    Each chunk gets full metadata for citations.
    """
    words = text.split()
    chunks = []

    if len(words) <= MAX_WORDS_PER_CHUNK:
        # Single chunk for this page
        if len(words) >= MIN_CHUNK_WORDS:
            chunks.append({
                "text": text,
                "doc_id": doc_id,
                "doc_name": doc_name,
                "page_num": page_num,
                "chunk_index": 0,
                "extraction_method": extraction_method,
            })
    else:
        # Sliding window chunking
        step = MAX_WORDS_PER_CHUNK - CHUNK_OVERLAP_WORDS
        chunk_idx = 0
        for start in range(0, len(words), step):
            chunk_words = words[start:start + MAX_WORDS_PER_CHUNK]
            if len(chunk_words) < MIN_CHUNK_WORDS:
                break
            chunks.append({
                "text": " ".join(chunk_words),
                "doc_id": doc_id,
                "doc_name": doc_name,
                "page_num": page_num,
                "chunk_index": chunk_idx,
                "extraction_method": extraction_method,
            })
            chunk_idx += 1

    return chunks


def index_document(doc_id: str, doc_name: str, pages: list[PageData]) -> int:
    """
    Index all pages of a document into ChromaDB.
    Returns number of chunks indexed.
    """
    collection = _get_collection()

    all_chunks = []

    for page in pages:
        # Main text chunks
        page_chunks = _chunk_text(
            page.text,
            page.page_num,
            doc_id,
            doc_name,
            page.extraction_method
        )
        all_chunks.extend(page_chunks)

        # Table chunks (each table is its own chunk)
        for t_idx, table_text in enumerate(page.tables):
            if len(table_text.split()) >= MIN_CHUNK_WORDS:
                all_chunks.append({
                    "text": f"[TABLE from {doc_name}, page {page.page_num}]\n{table_text}",
                    "doc_id": doc_id,
                    "doc_name": doc_name,
                    "page_num": page.page_num,
                    "chunk_index": 1000 + t_idx,  # Offset to avoid collision
                    "extraction_method": "table",
                })

    if not all_chunks:
        logger.warning(f"No chunks generated for doc {doc_id}")
        return 0

    # Generate embeddings
    texts = [c["text"] for c in all_chunks]
    embeddings = embedder.embed_chunks(texts)

    # Build IDs and metadatas
    ids = [
        f"{doc_id}_{c['page_num']}_{c['chunk_index']}"
        for c in all_chunks
    ]
    metadatas = [
        {
            "doc_id": c["doc_id"],
            "doc_name": c["doc_name"],
            "page_num": c["page_num"],
            "chunk_index": c["chunk_index"],
            "extraction_method": c["extraction_method"],
        }
        for c in all_chunks
    ]

    # Upsert (safe for re-indexing same doc)
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )

    logger.info(f"Indexed {len(all_chunks)} chunks for doc {doc_id}")

    # Update BM25 index incrementally
    bm25_index.add_chunks(all_chunks)

    return len(all_chunks)


def search(query: str, n_results: int = 5, doc_ids: list[str] | None = None) -> list[dict]:
    """
    Search for relevant chunks using cosine similarity.
    If doc_ids is provided, restricts results to chunks belonging to those documents
    (used for auth-scoped retrieval — public docs + the current user's own docs).
    Returns list of {text, doc_name, doc_id, page_num, distance}.
    """
    collection = _get_collection()

    if collection.count() == 0:
        return []

    if doc_ids is not None and len(doc_ids) == 0:
        # Caller is scoped but has access to nothing — short-circuit
        return []

    query_embedding = embedder.embed_query(query)
    where_filter = {"doc_id": {"$in": doc_ids}} if doc_ids is not None else None

    try:
        query_kwargs = dict(
            query_embeddings=[query_embedding],
            n_results=min(n_results, collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        if where_filter is not None:
            query_kwargs["where"] = where_filter

        results = collection.query(**query_kwargs)

        chunks = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, dists):
            chunks.append({
                "text": doc,
                "doc_name": meta.get("doc_name", "unknown"),
                "doc_id": meta.get("doc_id", ""),
                "page_num": meta.get("page_num", 1),
                "distance": dist,
                "extraction_method": meta.get("extraction_method", ""),
            })

        logger.info(f"Search '{query}' returned {len(chunks)} chunks, distances: {[c['distance'] for c in chunks]}")
        return chunks

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []


def delete_document(doc_id: str) -> bool:
    """Remove all chunks for a document from ChromaDB and BM25 index."""
    try:
        collection = _get_collection()
        collection.delete(where={"doc_id": doc_id})
        bm25_index.remove_doc(doc_id)
        logger.info(f"Deleted chunks for doc {doc_id}")
        return True
    except Exception as e:
        logger.error(f"Delete failed for {doc_id}: {e}")
        return False


def get_document_count() -> int:
    """Return total number of indexed chunks."""
    try:
        return _get_collection().count()
    except Exception:
        return 0


def get_all_chunks() -> list[dict]:
    """
    Fetch all chunks from ChromaDB for BM25 index initialization.
    Returns list of {text, doc_id, doc_name, page_num, chunk_index, extraction_method}.
    """
    try:
        collection = _get_collection()
        if collection.count() == 0:
            return []
        results = collection.get(include=["documents", "metadatas"])
        docs_list  = results.get("documents") or []
        metas_list = results.get("metadatas") or []
        chunks = []
        for text, meta in zip(docs_list, metas_list):
            chunks.append({
                "text": text,
                "doc_id": meta.get("doc_id", ""),
                "doc_name": meta.get("doc_name", "unknown"),
                "page_num": meta.get("page_num", 1),
                "chunk_index": meta.get("chunk_index", 0),
                "extraction_method": meta.get("extraction_method", ""),
            })
        return chunks
    except Exception as e:
        logger.error(f"get_all_chunks failed: {e}")
        return []
