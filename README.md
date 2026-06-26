# Document Intelligence + Agentic RAG

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-14-000000?logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=111111)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![ChromaDB](https://img.shields.io/badge/Vector%20DB-Chroma%20Cloud-6E56CF)
![Backblaze](https://img.shields.io/badge/Object%20Storage-Backblaze%20B2-E21E29?logo=backblaze&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Render](https://img.shields.io/badge/Backend-Render-46E3B7?logo=render&logoColor=white)
![Vercel](https://img.shields.io/badge/Frontend-Vercel-000000?logo=vercel&logoColor=white)

A full-stack, **deployed** app for document ingestion, parsing, classification, indexing, and grounded Q&A with citations - containerized for local development and running in production on Render, Vercel, and Chroma Cloud.

**Live demo:** https://doc-intel-mu.vercel.app

## Why this project

This repository gives you a complete pipeline:

- Upload PDFs, text files, and images
- Extract and normalize content (PyMuPDF text + table extraction)
- Classify documents with Groq (llama-3.1-8b-instant)
- Index chunks for semantic (vector) + lexical (BM25) retrieval
- Ask questions and get answers with inline citations and page previews

## Highlights

- FastAPI backend with clear route separation
- Next.js 14 frontend with upload, chat, and document preview workflows
- **Chroma Cloud** vector store (persistent, not tied to a single server's disk) plus BM25 keyword retrieval, fused via Reciprocal Rank Fusion
- **Postgres-backed metadata** - document status, classification, and chunk counts persist independently of any single server instance
- **Backblaze B2 object storage** - uploaded originals and rendered page images persist independently of any single server's local disk, surviving redeploys
- **Dockerized** backend + frontend with `docker-compose` for one-command local orchestration matching production architecture
- Streaming (SSE) and non-streaming chat endpoints
- Deployed end-to-end: FastAPI on Render, Next.js on Vercel, vectors on Chroma Cloud, metadata on Render Postgres, files on Backblaze B2

## Demo and Screenshots

Use this section for quick visual orientation when you share the project.

Suggested captures:

1. Landing page (`frontend/app/page.tsx`)
2. Upload workflow with progress states
3. Chat response showing inline citations
4. Document preview modal with page navigation

<img width="1918" height="902" alt="landing" src="https://github.com/user-attachments/assets/7eff8ecb-472e-4bb2-9259-6e45461016b3" />

<img width="1918" height="868" alt="upload-progress" src="https://github.com/user-attachments/assets/1b86337c-6b75-453f-8b90-298f83200dcd" />

<img width="1918" height="665" alt="chat-citations" src="https://github.com/user-attachments/assets/707de54f-1750-4ab7-af8d-82d8c68b9212" />

<img width="842" height="782" alt="doc-preview" src="https://github.com/user-attachments/assets/82cc02ea-af02-4a76-bbf1-1ebf5bc79443" />

## Architecture

```mermaid
flowchart LR
    A[Frontend Next.js — Vercel] --> B[FastAPI Routers — Render]
    B --> C[Upload Pipeline]
    C --> D[Parser — PyMuPDF]
    C --> E[Classifier — Groq LLM]
    D --> F[Chunking + ONNX Embeddings]
    F --> G[Chroma Cloud]
    F --> H[BM25 Index]
    C --> P[(Postgres — Render)]
    C --> S[(Backblaze B2)]
    A --> I[Chat API]
    I --> J[RAG Agent]
    J --> G
    J --> H
    J --> A
```

**Deployment topology:**

| Layer | Local Dev | Production |
|---|---|---|
| Frontend | Docker container (`localhost:3000`) | Vercel |
| Backend | Docker container (`localhost:8000`) | Render Web Service |
| Metadata DB | Docker Postgres container | Render Managed Postgres |
| Vector store | Chroma Cloud (shared with prod) | Chroma Cloud |
| File storage | Backblaze B2 (shared with prod) | Backblaze B2 |

## Repository Layout

```text
backend/
  main.py                  FastAPI app entrypoint
  Dockerfile               Backend container build
  limiter.py               Shared rate limiter
  requirements.txt         Python dependencies
  models/
    document.py            Request/response Pydantic models
    db.py                   SQLAlchemy models + Postgres session/engine
  routers/                 upload, chat, documents endpoints
  services/
    parser.py               PDF/text parsing (PyMuPDF)
    classifier.py            LLM-based document classification
    embedder.py              ONNX embedding function (Chroma's built-in MiniLM)
    vector_store.py          Chroma Cloud client + hybrid search
    document_repo.py         Postgres data-access layer (replaces old JSON metadata)
    object_storage.py        Backblaze B2 (S3-compatible) client for files + page images
    rag_agent.py             Retrieval orchestration + answer synthesis
    bm25_index.py            In-memory BM25 keyword index
    reranker.py              Cross-encoder re-ranking
  sample_docs/             Sample documents for demoing
  storage/                 Local scratch space during processing (uploaded files and
                           rendered page images are persisted to Backblaze B2 after
                           successful indexing, then removed from local disk)
frontend/
  Dockerfile               Frontend container build
  package.json             Next scripts and deps
  app/                     App Router pages
  components/              Reusable UI modules
  lib/                     API client and local storage helpers
docker-compose.yml         Orchestrates backend + frontend + postgres locally
```

## Tech Stack

- **Backend:** FastAPI, Uvicorn, Pydantic, SlowAPI, SQLAlchemy
- **Parsing:** PyMuPDF, pdfplumber (table extraction)
- **Retrieval:** Chroma Cloud (ONNX MiniLM embeddings), BM25, cross-encoder re-ranking
- **Metadata storage:** PostgreSQL (Render Managed Postgres in prod, Dockerized Postgres locally)
- **File storage:** Backblaze B2 (S3-compatible, via `boto3`)
- **LLM:** Groq (`groq` SDK) - llama-3.3-70b-versatile (RAG) + llama-3.1-8b-instant (classification)
- **Frontend:** Next.js 14, React 18, TypeScript, Tailwind CSS
- **Infra:** Docker, docker-compose, Render, Vercel, Chroma Cloud, Backblaze B2

## Prerequisites

- Docker Desktop (recommended path - see Quickstart below)
- Or, for a non-Docker setup: Python 3.11+, Node.js 18+
- Groq API key (free at https://console.groq.com)
- Chroma Cloud account (free tier - https://trychroma.com)
- Backblaze B2 account (free tier, 10GB - https://www.backblaze.com/sign-up/cloud-storage)

## Quickstart (Docker - recommended)

This is the fastest way to get the full stack running locally, identical to production architecture.

```bash
git clone https://github.com/ankitnegi-dev/DocIntel.git
cd DocIntel
```

Create `backend/.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
CHROMA_API_KEY=your_chroma_cloud_api_key
CHROMA_TENANT=your_chroma_tenant_id
CHROMA_DATABASE=your_chroma_database_name
B2_ENDPOINT_URL=https://s3.<region>.backblazeb2.com
B2_ACCESS_KEY_ID=your_b2_key_id
B2_SECRET_ACCESS_KEY=your_b2_application_key
B2_BUCKET_NAME=your_b2_bucket_name
ALLOWED_ORIGINS=http://localhost:3000
STORAGE_DIR=storage
SAMPLE_DOCS_DIR=sample_docs
```

Then:

```bash
docker-compose up --build
```

This starts three containers:
- `docintel-postgres` - Postgres 16, healthcheck-gated
- `docintel-backend` - FastAPI on `:8000`, waits for Postgres to be healthy, auto-creates tables on startup
- `docintel-frontend` - Next.js on `:3000`

Open:

- Frontend: http://localhost:3000
- Backend docs: http://localhost:8000/docs
- Backend health: http://localhost:8000/health

## Quickstart (without Docker)

### 1. Backend

```bash
cd backend
python -m venv .venv
powershell -ExecutionPolicy Bypass -File .venv\Scripts\Activate.ps1   # Windows
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Without a `DATABASE_URL` set, the backend falls back to a local SQLite file (`local_fallback.db`) so it still runs - but production and Docker both use Postgres.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

If PowerShell blocks `npm.ps1`, use `npm.cmd install` / `npm.cmd run dev` instead.

## First 5 Minutes Validation

1. Start the stack (`docker-compose up --build`, or both servers individually).
2. Open the Upload page and upload one of `backend/sample_docs/*`.
3. Confirm the Processing Queue shows: Upload -> Parse -> Classify -> Index -> Done.
4. Open the Chat page and ask a question about the uploaded document.
5. Confirm the response contains inline citations like `[DocName, Page N]` with a page thumbnail.

## Configuration

### Backend `.env`

```env
GROQ_API_KEY=your_groq_api_key_here
CHROMA_API_KEY=your_chroma_cloud_api_key
CHROMA_TENANT=your_chroma_tenant_id
CHROMA_DATABASE=your_chroma_database_name
B2_ENDPOINT_URL=https://s3.<region>.backblazeb2.com
B2_ACCESS_KEY_ID=your_b2_key_id
B2_SECRET_ACCESS_KEY=your_b2_application_key
B2_BUCKET_NAME=your_b2_bucket_name
ALLOWED_ORIGINS=http://localhost:3000
MAX_FILE_SIZE_MB=20
STORAGE_DIR=storage
SAMPLE_DOCS_DIR=sample_docs
# Optional - only needed outside Docker/Render where it's injected automatically:
# DATABASE_URL=postgresql://user:password@host:5432/dbname
```

Get a free Groq API key at https://console.groq.com -> API Keys -> Create API Key.
Get free Chroma Cloud credentials at https://trychroma.com -- create a project, then generate an API key from the Settings page.
Get free Backblaze B2 credentials at https://www.backblaze.com -- create a private bucket, then generate an Application Key scoped to that bucket.

### Frontend `.env.local`

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## API Overview

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/upload` | Upload one document |
| POST | `/bulk-upload` | Upload multiple documents |
| GET | `/status/{doc_id}` | Check processing status |
| POST | `/chat` | Ask question and get full response |
| POST | `/chat/stream` | Stream response with SSE |
| GET | `/documents` | List indexed docs (from Postgres) |
| GET | `/documents/{doc_id}` | Get document metadata (from Postgres) |
| DELETE | `/documents/{doc_id}` | Delete document (Postgres row + Chroma vectors + B2 files) |
| POST | `/documents/{doc_id}/reindex` | Re-index document |
| GET | `/page-image` | Get rendered page image |
| GET | `/health` | Service health and Chroma index count |

## Core Behavior

### Upload and Parsing

- Uses SHA-256 content hashing for safe, deduplicated storage
- Validates extension, Content-Type, and byte-level MIME when available
- Scans PDFs for suspicious markers before processing
- Documents with zero extractable text (e.g. scanned PDFs without OCR support) are correctly marked `status: error` with a clear reason, rather than falsely reporting success

### Metadata Persistence

- All document metadata (filename, status, classification, chunk count, error messages) is stored in **Postgres**, not flat JSON files
- A `services/document_repo.py` repository layer mediates all reads/writes -- routers never touch SQLAlchemy directly
- Postgres tables are auto-created on startup via `init_db()` -- safe to call on every boot

### File Persistence

- Local disk (`storage/uploads/`, `storage/pages/`) is treated as **scratch space only** during processing -- the parser needs local file paths, so files land there first
- After successful indexing, the original file and all rendered page images are uploaded to **Backblaze B2** (S3-compatible) via `services/object_storage.py`, then deleted from local disk
- `/page-image` tries B2 first and falls back to local disk, so documents indexed before this migration still work
- This design means `parser.py` needed no changes -- B2 wraps around the existing local-disk-based parsing logic rather than replacing it

### Retrieval and Answering

- Semantic retrieval from **Chroma Cloud** (ONNX MiniLM embeddings -- no GPU/torch dependency, keeps the backend lightweight enough for free-tier hosting)
- BM25 lexical retrieval complement, fused via Reciprocal Rank Fusion
- Cross-encoder reranking for final context quality
- Inline citation extraction and page linkage
- Relevance threshold tuned empirically against Chroma Cloud's distance scale (see Notes for Maintainers)

### Frontend Experience

- Upload flow with per-file progress states (Upload -> Parse -> Classify -> Index -> Done)
- Chat with citation cards, page thumbnails, and follow-up prompts
- Document sidebar with delete, reindex, and preview actions
- Markdown export for chat transcripts

## Security Notes

- Rate limits applied to upload and chat routes
- File size constraints enforced during upload
- Page image endpoint validates `doc_id` and resolved path (prevents directory traversal)
- Stored files use SHA-256 hashed filenames -- original filenames never touch the filesystem path
- Security headers added on backend responses
- CORS behavior controlled by environment settings

**Known limitations / what's next (see Roadmap):**
- No user authentication yet -- all documents are in a single shared namespace
- In-memory processing-status dict resets on restart (Postgres row remains as source of truth, but live progress percentages are lost mid-upload during a redeploy)
- Background tasks run synchronously in-process (FastAPI `BackgroundTasks`) rather than via a real job queue -- fine at current scale, but won't survive a server restart mid-job

## Troubleshooting

### Docker: "failed to connect to the docker API"

Docker Desktop isn't running. Launch it from the Start Menu and wait for the tray icon to settle before running `docker-compose` commands.

### Backend container restart-looping

Check `docker-compose logs backend --tail 50`. The most common cause during development is a Python `IndentationError`/`TabError` from mixed tabs/spaces after a manual edit -- open the file in VS Code and run "Convert Indentation to Spaces".

### PowerShell blocks npm

Use `npm.cmd`:

```powershell
npm.cmd install
npm.cmd run dev
```

### Frontend cannot reach backend

- Ensure backend is running and reachable on the port `NEXT_PUBLIC_API_URL` points to
- Confirm CORS (`ALLOWED_ORIGINS`) allows the frontend's origin
- In Docker, the frontend talks to the backend via `http://localhost:8000` from the browser (not the Docker network alias), since `NEXT_PUBLIC_API_URL` is baked in at build time for the browser to use directly

### "No relevant documents found" on a real, indexed document

Check `chunk_count` for that document via `/documents` or directly in Postgres -- if it's `0`, the document had no extractable text (commonly a scanned PDF; OCR support was removed to keep the backend within free-tier memory limits -- see Notes for Maintainers).

### Out of memory on Render free tier

Render's free tier caps at 512MB RAM. Avoid loading heavy ML libraries (`torch`, `sentence-transformers`, `easyocr`) at import time or on startup -- load them lazily on first use, or avoid them entirely (this project uses Chroma's built-in ONNX embedding function instead of `sentence-transformers` for this reason).

### Upload hangs or times out ("the read operation timed out")

This is almost always the ONNX embedding model re-downloading (~80MB from Chroma's CDN) rather than an actual B2/network failure -- check `docker-compose logs backend` for an `onnx.tar.gz` download progress line. In Docker, make sure the `onnx_cache` volume is mounted to `/root/.cache` so the model persists across container rebuilds instead of re-downloading every time. On Render, this download happens once per cold start and is unavoidable on the free tier, but should not repeat on every request.

## Deployment

This project is deployed across three platforms:

### Backend -> Render

- **Root Directory:** `backend`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Environment variables:** `GROQ_API_KEY`, `CHROMA_API_KEY`, `CHROMA_TENANT`, `CHROMA_DATABASE`, `B2_ENDPOINT_URL`, `B2_ACCESS_KEY_ID`, `B2_SECRET_ACCESS_KEY`, `B2_BUCKET_NAME`, `ALLOWED_ORIGINS`, `DATABASE_URL` (auto-populated by linking a Render Postgres instance)
- A separate **Render PostgreSQL** instance provides `DATABASE_URL` via its Internal Database URL

### Frontend -> Vercel

- **Root Directory:** `frontend`
- **Environment variables:** `NEXT_PUBLIC_API_URL` pointing to the Render backend URL

### Vector store -> Chroma Cloud

- Free-tier hosted vector database, shared between local Docker dev and production so indexed documents persist across redeploys and across environments

### File storage -> Backblaze B2

- Free-tier S3-compatible object storage (10GB), shared between local Docker dev and production
- Original files and rendered page images are written here after successful indexing; local disk is scratch space only

### Production checklist

- [x] Secrets via environment variables (never committed)
- [x] Explicit CORS origin handling
- [x] Persistent vector storage (Chroma Cloud) surviving redeploys
- [x] Persistent metadata storage (Postgres) surviving redeploys
- [x] Persistent file storage (Backblaze B2) surviving redeploys
- [ ] User authentication and per-user document scoping
- [ ] Structured logging / error monitoring (e.g. Sentry)
- [ ] Automated tests + CI

## Roadmap

This project is being actively extended beyond the original assignment scope as a learning exercise in production-grade system design:

- [x] Dockerize backend + frontend, orchestrate with `docker-compose`
- [x] Migrate vector storage from local ChromaDB to Chroma Cloud
- [x] Migrate document metadata from JSON files to Postgres (local + Render)
- [x] Migrate file storage (uploads, page images) to Backblaze B2 (S3-compatible)
- [ ] Add authentication and per-user document scoping
- [ ] Replace synchronous background tasks with a real job queue (Celery/Redis or `arq`)
- [ ] Add a retrieval evaluation harness (precision/recall against a labeled Q&A set)
- [ ] Add automated tests and CI

## Development Commands

**Docker (recommended):**

```bash
docker-compose up --build       # build + start everything
docker-compose down             # stop everything
docker-compose logs backend     # tail backend logs
docker exec -it docintel-postgres psql -U docintel -d docintel   # connect to local Postgres
```

**Backend (without Docker):**

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

**Frontend (without Docker):**

```bash
cd frontend
npm run dev
npm run build
npm run lint
```

## Notes for Maintainers

- `backend/main.py` no longer auto-indexes sample documents or warms up the embedding model on startup -- both were removed after causing out-of-memory crashes on Render's free tier. Use `backend/create_samples.py` or the `/upload` endpoint to seed sample documents instead.
- `backend/services/embedder.py` uses Chroma's built-in `ONNXMiniLM_L6_V2` embedding function rather than `sentence-transformers`, specifically to avoid pulling in `torch` (~1.5GB), which does not fit in Render's 512MB free-tier memory limit.
- `RELEVANCE_THRESHOLD` in `backend/services/rag_agent.py` was empirically retuned after migrating to Chroma Cloud + `chromadb==1.5.9`, since the cosine-distance scale shifted compared to the original local ChromaDB 0.5.x setup. If retrieval quality seems off after a ChromaDB version bump, check this value against real logged distances before assuming a code bug.
- `backend/routers/upload.py` and `backend/routers/documents.py` are fully migrated to Postgres via `services/document_repo.py`. `backend/create_samples.py` still writes to the legacy JSON metadata format -- it is a standalone seeding script, not part of the live request path, so this inconsistency is tracked but not urgent.
- File persistence to Backblaze B2 happens in `_persist_to_object_storage()` in `backend/routers/upload.py`, called right after successful indexing. It is best-effort: a B2 failure logs a warning but does not fail the upload, since the document is already indexed and usable from Postgres + Chroma Cloud alone.
- The ONNX embedding model (~80MB) is downloaded on first use and cached at `/root/.cache/chroma/onnx_models/`. In `docker-compose.yml`, this path is mounted to a named volume (`onnx_cache`) so it persists across container rebuilds -- without this, every `docker-compose up --build` re-downloads the model, which can take several minutes on a slow connection and looks like a hung upload.
- `frontend/lib/api.ts` is the central API client used by UI components.

## License

No license file is currently included in this repository. Add one before public distribution.