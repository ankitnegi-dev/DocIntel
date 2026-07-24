# Document Intelligence + Agentic RAG

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-14-000000?logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=111111)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![ChromaDB](https://img.shields.io/badge/Vector%20DB-Chroma%20Cloud-6E56CF)
![Backblaze](https://img.shields.io/badge/Object%20Storage-Backblaze%20B2-E21E29?logo=backblaze&logoColor=white)
![Redis](https://img.shields.io/badge/Job%20Queue-arq%20%2B%20Redis-DC382D?logo=redis&logoColor=white)
![JWT](https://img.shields.io/badge/Auth-JWT%20%2B%20bcrypt-000000?logo=jsonwebtokens&logoColor=white)
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
- **JWT authentication** - email/password accounts with bcrypt-hashed passwords; uploads are scoped per-user all the way through retrieval (chat only ever surfaces a user's own documents plus public/demo documents), while anonymous visitors can still use the public demo set with no login
- **Redis-backed job queue (arq)** - document processing runs in a separate worker process so an in-flight upload survives an API server restart/redeploy, rather than being silently lost like with in-process background tasks (fully implemented and tested locally; see Roadmap for production status)
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
    U[Browser] -->|JWT| A[Frontend Next.js - Vercel]
    A --> B[FastAPI Routers - Render]
    B --> AUTH[Auth: JWT + bcrypt]
    B --> C[Upload Pipeline]
    C -->|enqueue| Q[(Redis - arq)]
    Q --> W[Worker process]
    W --> D[Parser - PyMuPDF]
    W --> E[Classifier - Groq LLM]
    D --> F[Chunking + ONNX Embeddings]
    F --> G[Chroma Cloud]
    F --> H[BM25 Index]
    W --> P[(Postgres - Render)]
    W --> S[(Backblaze B2)]
    A --> I[Chat API]
    I --> J[RAG Agent]
    J -->|scoped by user_id| G
    J --> H
    J --> A
```

Local dev runs the full diagram above, including the Redis/worker path. Production currently skips the Redis/worker box — uploads there fail gracefully with a clear message instead (see Roadmap).

**Deployment topology:**

| Layer | Local Dev | Production |
|---|---|---|
| Frontend | Docker container (`localhost:3000`) | Vercel |
| Backend | Docker container (`localhost:8000`) | Render Web Service |
| Metadata DB | Docker Postgres container | Render Managed Postgres |
| Vector store | Chroma Cloud (shared with prod) | Chroma Cloud |
| File storage | Backblaze B2 (shared with prod) | Backblaze B2 |
| Job queue | Redis + arq worker (Docker containers) | Not provisioned - uploads return a clear 503 (see Roadmap) |

## Repository Layout

```text
backend/
  main.py                  FastAPI app entrypoint
  worker.py                arq worker settings/entrypoint (separate process from the API)
  tasks.py                 Background job functions run by the worker (parse->classify->index->persist)
  Dockerfile               Backend/worker container build (shared image, different start command)
  limiter.py               Shared rate limiter
  requirements.txt         Python dependencies
  models/
    document.py            Request/response Pydantic models
    db.py                   SQLAlchemy models (User, Document) + Postgres session/engine
  routers/                 upload, chat, documents, auth endpoints
  services/
    parser.py               PDF/text parsing (PyMuPDF)
    classifier.py            LLM-based document classification
    embedder.py              ONNX embedding function (Chroma's built-in MiniLM)
    vector_store.py          Chroma Cloud client + hybrid search (auth-scoped via doc_id filter)
    document_repo.py         Postgres data-access layer (documents + users)
    object_storage.py        Backblaze B2 (S3-compatible) client for files + page images
    job_queue.py             arq/Redis pool + job enqueue helper, used by the API process
    rag_agent.py             Retrieval orchestration + answer synthesis (auth-scoped retrieval)
    bm25_index.py            In-memory BM25 keyword index
    reranker.py              Cross-encoder re-ranking
    auth.py                  Password hashing (bcrypt) + JWT create/decode
    auth_deps.py              FastAPI dependencies for required/optional current-user extraction
  sample_docs/             Sample documents for demoing
  storage/                 Local scratch space during processing (uploaded files and
                           rendered page images are persisted to Backblaze B2 after
                           successful indexing, then removed from local disk)
frontend/
  Dockerfile               Frontend container build
  package.json             Next scripts and deps
  app/                     App Router pages (including login/, register/)
  components/              Reusable UI modules
  context/
    AuthContext.tsx         React context: current user, login/register/logout
  lib/                     API client (JWT auto-attached via Axios interceptor) and helpers
docker-compose.yml         Orchestrates backend + worker + frontend + postgres + redis locally
```

## Tech Stack

- **Backend:** FastAPI, Uvicorn, Pydantic, SlowAPI, SQLAlchemy
- **Auth:** JWT (python-jose), bcrypt password hashing (passlib)
- **Job queue:** arq (Redis-backed async job queue) - separate worker process from the API
- **Parsing:** PyMuPDF, pdfplumber (table extraction)
- **Retrieval:** Chroma Cloud (ONNX MiniLM embeddings), BM25, cross-encoder re-ranking
- **Metadata storage:** PostgreSQL (Render Managed Postgres in prod, Dockerized Postgres locally)
- **File storage:** Backblaze B2 (S3-compatible, via `boto3`)
- **LLM:** Groq (`groq` SDK) - llama-3.3-70b-versatile (RAG) + llama-3.1-8b-instant (classification)
- **Frontend:** Next.js 14, React 18, TypeScript, Tailwind CSS
- **Infra:** Docker, docker-compose, Render, Vercel, Chroma Cloud, Backblaze B2, Redis

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
JWT_SECRET_KEY=generate_a_random_64_char_hex_string
ALLOWED_ORIGINS=http://localhost:3000
STORAGE_DIR=storage
SAMPLE_DOCS_DIR=sample_docs
```

Generate a `JWT_SECRET_KEY` with: `python -c "import secrets; print(secrets.token_hex(32))"`

Then:

```bash
docker-compose up --build
```

This starts five containers:
- `docintel-postgres` - Postgres 16, healthcheck-gated
- `docintel-redis` - Redis 7, backs the job queue
- `docintel-backend` - FastAPI on `:8000`, waits for Postgres + Redis to be healthy, auto-creates tables on startup
- `docintel-worker` - arq worker process; runs the actual parse->classify->index->persist pipeline, separate from the API process
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
2. Register an account at `/register`, or log in if you already have one.
3. Open the Upload page and upload one of `backend/sample_docs/*`. The Processing Queue shows Queued, then flips to Indexed once the worker finishes (see Notes for Maintainers on the live-progress trade-off).
4. Open the Chat page and ask a question about the uploaded document - while logged in, this checks your own documents plus the public/demo set; log out and the same question should no longer find your private upload.
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
JWT_SECRET_KEY=generate_a_random_64_char_hex_string
ALLOWED_ORIGINS=http://localhost:3000
MAX_FILE_SIZE_MB=20
STORAGE_DIR=storage
SAMPLE_DOCS_DIR=sample_docs
# Optional - only needed outside Docker/Render where it's injected automatically:
# DATABASE_URL=postgresql://user:password@host:5432/dbname
# REDIS_URL=redis://localhost:6379
```

Get a free Groq API key at https://console.groq.com -> API Keys -> Create API Key.
Get free Chroma Cloud credentials at https://trychroma.com -- create a project, then generate an API key from the Settings page.
Get free Backblaze B2 credentials at https://www.backblaze.com -- create a private bucket, then generate an Application Key scoped to that bucket.
Generate `JWT_SECRET_KEY` with `python -c "import secrets; print(secrets.token_hex(32))"` -- use a different value per environment (local vs. production).

### Frontend `.env.local`

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## API Overview

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/auth/register` | Create a new account, returns a JWT |
| POST | `/auth/login` | Log in, returns a JWT |
| GET | `/auth/me` | Get the current logged-in user (requires token) |
| POST | `/upload` | Upload one document (requires login) |
| POST | `/bulk-upload` | Upload multiple documents (requires login) |
| GET | `/status/{doc_id}` | Check processing status |
| POST | `/chat` | Ask question and get full response (works logged-out on public docs; scoped to own+public docs when logged in) |
| POST | `/chat/stream` | Stream response with SSE (same auth-aware scoping as `/chat`) |
| GET | `/documents` | List documents visible to the caller (own + public, or public only if logged out) |
| GET | `/documents/{doc_id}` | Get document metadata (must be public or owned by caller) |
| DELETE | `/documents/{doc_id}` | Delete document (owner only; Postgres row + Chroma vectors + B2 files) |
| POST | `/documents/{doc_id}/reindex` | Re-index document (owner only) |
| GET | `/page-image` | Get rendered page image |
| GET | `/health` | Service health and Chroma index count |

## Core Behavior

### Upload and Parsing

- Uses SHA-256 content hashing for safe, deduplicated storage
- Validates extension, Content-Type, and byte-level MIME when available
- Scans PDFs for suspicious markers before processing
- Documents with zero extractable text (e.g. scanned PDFs without OCR support) are correctly marked `status: error` with a clear reason, rather than falsely reporting success

### Authentication & Authorization

- Email/password accounts, bcrypt-hashed passwords, JWT access tokens (7-day expiry)
- Uploading requires login. Every document has a nullable `user_id`: `NULL` means public/demo, otherwise it's owned by that user
- `/documents`, `/documents/{id}`, `/page-image`, and `/chat` use *optional* auth -- anonymous visitors can browse and ask questions about the public/demo document set with no login; logged-in users additionally see and can query their own private documents
- `DELETE` and `/reindex` require login *and* ownership (or the document being public)
- Retrieval is scoped at the vector-search layer, not just the listing layer: `rag_agent.py` asks Postgres for the caller's visible `doc_id`s and passes that as a Chroma `where` filter plus a BM25 post-filter, so a logged-out or different user genuinely cannot get an answer grounded in someone else's private document through chat -- this was verified directly (same question, with and without a token, against a private document) rather than assumed

### Job Queue (background processing)

- Uploads are enqueued as `arq` jobs (Redis-backed) and processed by a separate **worker** process (`worker.py` / `tasks.py`), not by the API process's `BackgroundTasks`
- This means an in-flight upload survives an API server restart or redeploy -- verified by restarting the backend mid-processing and confirming the worker completed the job independently and Postgres reflected the correct final state
- Trade-off: because processing now happens out-of-process, the fine-grained live progress the old in-process approach had (parsing 20% -> classifying 50% -> indexing 75%) is no longer tracked live. Status now reads `queued` -> `indexed`/`error`, sourced from Postgres. Durability was prioritized over granular live progress; see Roadmap for the frontend polish this leaves open

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
- Production has no Redis/worker provisioned -- uploads in production return a clear `503` explaining the job queue isn't available there, rather than hanging or crashing (this was a deliberate cost decision, not an oversight; see Roadmap)
- The frontend upload UI still expects granular live-progress stages that the job-queue architecture no longer produces -- functionally the upload completes correctly, but the "Waiting to start..." state can persist longer than expected before flipping to done
- Background jobs run at `max_jobs = 4` concurrency on a single local worker; no horizontal scaling or dead-letter/retry handling beyond arq's defaults

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

This is almost always the ONNX embedding model re-downloading (~80MB from Chroma's CDN) rather than an actual B2/network failure -- check `docker-compose logs worker` for an `onnx.tar.gz` download progress line (the model loads in the **worker** container, not the backend, since that's where indexing runs). In Docker, make sure the `onnx_cache` volume is mounted to `/root/.cache` so the model persists across container rebuilds instead of re-downloading every time.

### Upload returns 401 "Authentication required"

Uploading requires login. Register/log in via `/register` or `/login`, or check that the frontend is sending the `Authorization: Bearer <token>` header (the Axios interceptor in `lib/api.ts` does this automatically once a token is stored). `/chat` and `/documents` work without login too, but only against public/demo documents.

### Upload returns 503 "Background job queue is not available in this environment"

Expected in production, where no Redis instance is provisioned (see Roadmap). Locally, this means the `redis` container isn't running or `REDIS_URL` isn't reaching it -- check `docker-compose ps` and `docker-compose logs redis`.

### Uploaded document stuck at "queued" and never finishes

Check `docker-compose logs worker` (or the Render worker service logs, if one is provisioned) -- the API process only enqueues the job, it doesn't process it. If the worker container isn't running, jobs will sit in Redis indefinitely.

## Deployment

This project is deployed across three platforms:

### Backend -> Render

- **Root Directory:** `backend`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Environment variables:** `GROQ_API_KEY`, `CHROMA_API_KEY`, `CHROMA_TENANT`, `CHROMA_DATABASE`, `B2_ENDPOINT_URL`, `B2_ACCESS_KEY_ID`, `B2_SECRET_ACCESS_KEY`, `B2_BUCKET_NAME`, `JWT_SECRET_KEY`, `ALLOWED_ORIGINS`, `DATABASE_URL` (auto-populated by linking a Render Postgres instance)
- A separate **Render PostgreSQL** instance provides `DATABASE_URL` via its Internal Database URL
- **No `REDIS_URL` is currently set** -- production does not have a Redis/worker provisioned (see Roadmap). Uploads return a `503` with a clear explanation rather than failing silently or crashing.

### Frontend -> Vercel

- **Root Directory:** `frontend`
- **Environment variables:** `NEXT_PUBLIC_API_URL` pointing to the Render backend URL

### Vector store -> Chroma Cloud

- Free-tier hosted vector database, shared between local Docker dev and production so indexed documents persist across redeploys and across environments

### File storage -> Backblaze B2

- Free-tier S3-compatible object storage (10GB), shared between local Docker dev and production
- Original files and rendered page images are written here after successful indexing; local disk is scratch space only

### Job queue -> local only (for now)

- Redis + a dedicated worker service were built, deployed, and verified working on Render (a paid Key Value instance plus a free Background Worker service), then deliberately torn down after confirming the local implementation was solid -- the ongoing $7/month cost wasn't justified for a portfolio project at this stage
- The production API degrades gracefully: `services/job_queue.py` catches the Redis connection failure and `routers/upload.py` returns a `503` with a clear message, instead of hanging or throwing an unhandled exception
- Re-provisioning production support is a config-only change (create a Render Key Value instance + a Background Worker service running `arq worker.WorkerSettings`, add `REDIS_URL` to both) -- no code changes needed

### Production checklist

- [x] Secrets via environment variables (never committed)
- [x] Explicit CORS origin handling
- [x] Persistent vector storage (Chroma Cloud) surviving redeploys
- [x] Persistent metadata storage (Postgres) surviving redeploys
- [x] Persistent file storage (Backblaze B2) surviving redeploys
- [x] User authentication and per-user document scoping (enforced through retrieval, not just listing)
- [x] Background job queue implemented and tested for restart-durability (local only; graceful degradation in production)
- [ ] Structured logging / error monitoring (e.g. Sentry)
- [ ] Automated tests + CI

## Roadmap

This project is being actively extended beyond the original assignment scope as a learning exercise in production-grade system design:

- [x] Dockerize backend + frontend, orchestrate with `docker-compose`
- [x] Migrate vector storage from local ChromaDB to Chroma Cloud
- [x] Migrate document metadata from JSON files to Postgres (local + Render)
- [x] Migrate file storage (uploads, page images) to Backblaze B2 (S3-compatible)
- [x] Add authentication and per-user document scoping (JWT + bcrypt; enforced through chat retrieval, not just document listing)
- [x] Replace synchronous background tasks with a real job queue (arq + Redis) -- built, deployed, and verified on Render, then scoped back to local-only after weighing the ongoing cost against project stage
- [ ] Provision production Redis + worker again once there's a concrete reason to (e.g. real users, or as a paid-tier demo)
- [ ] Restore granular live upload progress in the frontend (currently shows queued/indexed only, since progress tracking moved out-of-process with the worker)
- [ ] Add a retrieval evaluation harness (precision/recall against a labeled Q&A set)
- [ ] Add automated tests and CI

## Development Commands

**Docker (recommended):**

```bash
docker-compose up --build       # build + start everything (postgres, redis, backend, worker, frontend)
docker-compose down             # stop everything
docker-compose logs backend     # tail API logs
docker-compose logs worker      # tail background job processing logs
docker exec -it docintel-postgres psql -U docintel -d docintel   # connect to local Postgres
```

**Backend (without Docker):**

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
# In a separate terminal, run the worker (requires a local Redis):
arq worker.WorkerSettings
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
- File persistence to Backblaze B2 happens in `tasks.py` (moved there from `upload.py` when processing became a separate worker job). It is best-effort: a B2 failure logs a warning but does not fail the job, since the document is already indexed and usable from Postgres + Chroma Cloud alone.
- The ONNX embedding model (~80MB) is downloaded on first use and cached at `/root/.cache/chroma/onnx_models/`. In `docker-compose.yml`, this path is mounted to a named volume (`onnx_cache`) on **both** the `backend` and `worker` services, since indexing (and therefore the model load) now happens in the worker container.
- `RELEVANCE_THRESHOLD` in `backend/services/rag_agent.py` was empirically retuned after migrating to Chroma Cloud + `chromadb==1.5.9`, since the cosine-distance scale shifted compared to the original local ChromaDB 0.5.x setup. If retrieval quality seems off after a ChromaDB version bump, check this value against real logged distances before assuming a code bug.
- `services/auth_deps.py` provides two dependencies: `get_current_user_required` (401s if no valid token) and `get_current_user_optional` (returns `None` instead of raising). Routes that should work for both anonymous and logged-in users -- `/documents`, `/documents/{id}`, `/page-image`, `/chat`, `/chat/stream` -- use the optional variant and then filter by `user_id` themselves.
- Auth-scoped retrieval is implemented at the vector-search layer (`vector_store.search(..., doc_ids=...)` builds a Chroma `where: {"doc_id": {"$in": [...]}}` filter) plus a BM25 post-filter in `rag_agent._hybrid_search`, not just at the document-listing layer. This was a deliberate choice: filtering only in `/documents` would have left `/chat` able to answer questions using content from documents the caller can't even see listed.
- `worker.py` / `tasks.py` run as a separate Docker service (`docintel-worker` locally) from the API (`docintel-backend`), sharing the same image but with a different start command (`arq worker.WorkerSettings` vs `uvicorn main:app`). This is intentional -- an API process restart (e.g. on every Render redeploy) does not affect an in-flight job, because the job lives in Redis and the worker is a wholly separate process.
- `frontend/lib/api.ts` is the central API client used by UI components; it attaches the JWT to every request via an Axios request interceptor, so individual API functions don't need to handle auth headers manually.

## License

No license file is currently included in this repository. Add one before public distribution.