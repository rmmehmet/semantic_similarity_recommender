<h1 align="center">AltayAI</h1>

<p align="center">
  <strong>Retrieval-augmented academic document platform for project originality analysis and PDF chat.</strong><br/>
  Upload academic papers, search them semantically, get grounded LLM analyses of a new project idea,<br/>
  and chat with your own documents using streamed, source-cited answers.
</p>

<p align="center">
  <a href="https://altayai.duckdns.org/"><strong>Live Demo</strong></a>
  &nbsp;·&nbsp;
  <a href="#architecture">Architecture</a>
  &nbsp;·&nbsp;
  <a href="#rag-pipeline">RAG Pipeline</a>
  &nbsp;·&nbsp;
  <a href="#installation--local-development">Installation</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10-3776AB?style=flat-square&logo=python&logoColor=white"/>
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white"/>
  <img alt="React" src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black"/>
  <img alt="Vite" src="https://img.shields.io/badge/Vite-8-646CFF?style=flat-square&logo=vite&logoColor=white"/>
</p>
<p align="center">
  <img alt="sentence-transformers" src="https://img.shields.io/badge/sentence--transformers-5.4-FFD21E?style=flat-square&logo=huggingface&logoColor=black"/>
  <img alt="Milvus" src="https://img.shields.io/badge/Milvus-2.4-00A1EA?style=flat-square&logo=milvus&logoColor=white"/>
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white"/>
  <img alt="OpenRouter" src="https://img.shields.io/badge/OpenRouter-LLM_API-94A3B8?style=flat-square&logo=openrouter&logoColor=white"/>
</p>
<p align="center">
  <img alt="Docker Compose" src="https://img.shields.io/badge/Docker_Compose-2496ED?style=flat-square&logo=docker&logoColor=white"/>
  <img alt="nginx" src="https://img.shields.io/badge/nginx-1.27-009639?style=flat-square&logo=nginx&logoColor=white"/>
  <img alt="Google Cloud" src="https://img.shields.io/badge/Google_Cloud-Compute_Engine-4285F4?style=flat-square&logo=googlecloud&logoColor=white"/>
</p>

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [RAG Pipeline](#rag-pipeline)
- [Technology Stack](#technology-stack)
- [Technical Architecture](#technical-architecture)
- [Data & Storage](#data--storage)
- [Search & Retrieval](#search--retrieval)
- [Project Structure](#project-structure)
- [Security](#security)
- [Deployment](#deployment)
- [Installation & Local Development](#installation--local-development)
- [API Overview](#api-overview)
- [Engineering Decisions](#engineering-decisions)
- [Limitations & Future Improvements](#limitations--future-improvements)
- [Author](#author)

---

## Overview

AltayAI was built for university senior design project evaluation (BM498). Students and faculty need to know
whether a proposed project overlaps with existing work, and to get answers from long academic PDFs without
reading them end to end. AltayAI addresses both with a retrieval-augmented generation (RAG) system over a
**private, per-user document library**.

**How it works**

1. **Ingestion.** A user uploads a PDF. The backend extracts the title, abstract and full text with PyMuPDF,
   detects section headings and page boundaries, splits the text into sentence-aware chunks and embeds them
   with a multilingual sentence-transformers model. Text and metadata go to PostgreSQL. Vectors go to Milvus.
2. **Retrieval.** Each query runs a dense vector search in Milvus and a lexical full-text search in PostgreSQL
   in parallel. The results are merged with Reciprocal Rank Fusion and reordered by an LLM reranker.
3. **Generation.** The top chunks, labelled with document, section and page, are assembled into a grounded
   prompt and sent to an LLM through OpenRouter. Chat answers are streamed to the browser over Server-Sent
   Events and saved together with their sources.

The interface and prompts are Turkish-first. The text pipeline handles Turkish abbreviations, Turkish stemming
in full-text search and a multilingual embedding model for mixed Turkish and English academic content.

---

## Key Features

### Retrieval-Augmented Generation

| Feature | Description |
|---|---|
| **PDF Chat** | Ask questions about one PDF, a selected subset or the whole library. Answers are streamed over SSE and cite the source document and section. |
| **Hybrid retrieval** | Milvus HNSW vector search and PostgreSQL full-text search (`simple` + `turkish` configurations), fused with Reciprocal Rank Fusion. |
| **LLM reranking** | Fused candidates are reordered by an LLM call. If the call fails, the fused order is kept. |
| **Conversational retrieval** | Follow-up questions are expanded with the previous two stored messages before retrieval. |
| **Persistent conversations** | Conversations and messages, including cited sources, are stored server-side and restored when the user switches conversations. |

### Project Originality Analysis

| Feature | Description |
|---|---|
| **Three search modes** | `title`, `abstract` and `fulltext` similarity search, each backed by its own Milvus collection. |
| **Structured LLM analysis** | Returns a research field, risk level, similarity analysis, original aspects, improvement suggestions, alternative topics with novelty scores and a revised title as JSON. |
| **PDF-based evaluation** | In `fulltext` mode, a project PDF can be uploaded and compared against the library with chunk-level evidence. |

### Document Processing

| Feature | Description |
|---|---|
| **Structure-aware extraction** | Headings are detected from font size, bold weight, numbering, Roman numerals and keywords, and stored as section and page metadata. |
| **Sentence-aware chunking** | Turkish-aware sentence splitting, 850-character chunks, one-sentence overlap, chunks never cross section boundaries, bibliography excluded. |
| **PDF Splitter** | Splits multi-paper proceedings into individual papers using a font-size threshold, with preview and per-section download. |
| **De-duplication** | SHA-256 content hashing detects re-uploads under a different file name. Name conflicts require an explicit overwrite. |

### Platform

| Feature | Description |
|---|---|
| **Multi-tenancy** | Every PostgreSQL row, Milvus vector and stored file is scoped to its owner's `user_id`. |
| **Authentication** | Email and password registration, JWT in an httpOnly cookie, profile editing and password change with session revocation. |
| **Usage controls** | Per-IP rate limits and a per-user daily quota on endpoints that call the LLM. |
| **Store consistency** | A `milvus_synced` flag on each paper. The admin `reconcile` endpoint re-embeds unsynced papers and removes orphaned vectors. |

---

## Architecture

![AltayAI Architecture](docs/architecture.svg)

All services run as Docker Compose containers on a single Google Cloud Compute Engine VM. nginx is the only
publicly exposed service. It terminates TLS, serves the React build at `/` and proxies `/api/*` to the FastAPI
backend on port 8000. Because the frontend and API share one origin, the session cookie works without
cross-origin configuration.

---

## RAG Pipeline

![RAG Pipeline](docs/rag-pipeline.svg)

The architecture diagram shows the request path through the system, and the pipeline diagram shows the AI
processing path, so a separate data-flow diagram is not included.

---

## Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, React Router 7, Vite 8, axios, Fetch API (SSE stream reader), GSAP |
| **Backend** | Python 3.10, FastAPI 0.111, Uvicorn, Pydantic 2, asyncpg, Alembic |
| **Document processing** | PyMuPDF 1.27 |
| **AI / ML** | sentence-transformers 5.4 (`paraphrase-multilingual-mpnet-base-v2`), PyTorch (CPU build) |
| **LLM** | OpenRouter Chat Completions API, default model `meta-llama/llama-3.1-8b-instruct` |
| **Vector search** | Milvus 2.4 standalone (etcd + MinIO), pymilvus, HNSW index, COSINE metric |
| **Relational database** | PostgreSQL 16 with `tsvector` generated columns and GIN indexes |
| **Authentication** | PyJWT (HS256), bcrypt, email-validator, phonenumbers |
| **Infrastructure** | Docker, Docker Compose, nginx 1.27, Let's Encrypt (certbot), Google Cloud Compute Engine |

---

## Technical Architecture

| Component | Responsibility | Input | Output | Communicates with |
|---|---|---|---|---|
| **nginx (edge)** | TLS termination, HTTP→HTTPS redirect, routing | Browser HTTPS requests | Proxied requests | Frontend container (`/`), backend (`/api/`) |
| **Frontend** | SPA for auth, library, splitter, suggestion and chat | User actions | REST calls, SSE stream consumption | Backend via `/api` with cookie credentials |
| **Routers** (`backend/routers`) | HTTP contract, validation, auth and rate-limit dependencies | JSON / multipart requests | JSON, PDF streams, SSE events | Service layer |
| **Auth** (`services/auth.py`, `security.py`) | Password hashing, JWT issuing and validation, admin checks | Credentials, session cookie | User claims or 401 / 403 | PostgreSQL (`token_version`) |
| **Text preprocessing** | PDF text extraction, title and abstract detection, heading and page markers | PDF bytes | Marked-up full text, title, abstract | Chunking service |
| **Chunking** | Sentence-aware, section-bounded chunking with metadata | Marked-up full text | Chunks with `section`, `subsection`, `page_start`, `page_end` | Embedding model, PostgreSQL |
| **Embedding model** | Encodes titles, abstracts, chunks and queries | Text | 768-d normalized vectors | Milvus |
| **Hybrid search** | Vector and keyword retrieval, RRF fusion | Query vector and text | Ranked, de-duplicated chunks | Milvus, PostgreSQL, reranker |
| **Reranker** | LLM-based relevance ordering | Query, candidate texts | Index permutation | OpenRouter |
| **Chat service** | RAG orchestration, history, context building, streaming | Message, PDF scope, conversation id | Token stream and sources | Hybrid search, OpenRouter, PostgreSQL |
| **Suggest service** | Title / abstract / fulltext similarity and RAG analysis | Query text and optional PDF | Ranked papers and structured JSON analysis | Milvus, PostgreSQL, OpenRouter |
| **OpenRouter client** | Shared HTTP client with retries and streaming | Chat messages and parameters | Completion text or token iterator | OpenRouter API |

### How the AI pipeline runs

**Ingestion** (`POST /db/add`, `routers/database_router.py`)

1. The upload is checked for the `%PDF-` magic bytes and the size limit, then hashed with SHA-256 for
   per-user de-duplication. The original file is written to `storage/pdfs/{user_id}/`.
2. `text_preprocessing.py` extracts the title (PDF metadata, otherwise the largest font on the first page),
   the full text with inline `<<<SECTION:…>>>`, `<<<SUBSECTION:…>>>` and `<<<PAGE:n>>>` markers, and the
   abstract (from a detected abstract section, with a keyword-based fallback).
3. `chunking_service.py` builds one title record, one abstract chunk (up to 500 characters, cut at a sentence
   boundary) and full-text chunks of up to 850 characters with a one-sentence overlap. A new section always
   starts a new chunk. Chunks shorter than 200 characters are merged into the previous chunk. Sentences in a
   references or bibliography section are excluded.
4. All texts are embedded in one batch. The paper and its chunks are written to PostgreSQL with
   `milvus_synced = FALSE`. The three Milvus inserts and flushes then run concurrently, and the flag is set
   to `TRUE` only after they succeed.

**Chat** (`POST /chat/message/stream`, `services/chat_service.py`)

1. The retrieval query is the user message prefixed with the last two stored messages of the conversation.
2. Vector search on `liftup_fulltext` and PostgreSQL full-text search run concurrently with the same
   `user_id` and optional `pdf_name` scope. Either search can fail without stopping the request.
3. The results are merged with RRF, reranked by the LLM and formatted as
   `[pdf_name (section > subsection, s.pages)] chunk text`.
4. The system prompt instructs the model to answer only from the provided context and to say so when the
   answer is not in it. The last 10 stored messages are included as history.
5. Tokens are relayed as SSE `chunk` events, followed by `done` (with `conversation_id` and sources) or
   `error`. The question and answer are persisted only after a successful generation. A conversation created
   for a failed first message is deleted.

---

## Data & Storage

AltayAI keeps a strict separation between stores:

- **PostgreSQL** is the system of record: users, document text, chunks, chat history and lexical search.
- **Milvus** holds only vectors and the minimal payload needed for retrieval.
- A Docker volume holds the original PDFs.

Milvus can be rebuilt completely from PostgreSQL. The `reconcile` endpoint and the scripts in
`backend/scripts/` do this.

### PostgreSQL

Schema is managed by Alembic (`backend/migrations/versions/`).

| Table | Purpose | Key columns |
|---|---|---|
| `users` | Accounts | `email` (unique), `phone` (unique, E.164), `password_hash`, `role` (`user` / `admin`), `is_active`, `token_version` |
| `papers` | One row per uploaded document | `user_id` → `users`, `pdf_name`, `raw_title`, `abstract`, `fulltext`, `book_name`, `year`, `content_hash`, `milvus_synced` |
| `chunks` | Chunk text and metadata | `paper_id` → `papers`, `chunk_idx`, `chunk_type` (`title` / `abstract` / `fulltext`), `section`, `subsection`, `page_start`, `page_end`, `tsv`, `tsv_turkish` |
| `chat_conversations` | Conversation headers | `user_id` → `users`, `title`, `pdf_names` (JSONB scope), `created_at`, `updated_at` |
| `chat_messages` | Conversation turns | `conversation_id` → `chat_conversations`, `role`, `content`, `sources` (JSONB) |

All foreign keys use `ON DELETE CASCADE`. Deleting a user removes their papers, chunks and conversations.

**Notable indexes**

| Index | Definition | Purpose |
|---|---|---|
| `idx_papers_user_pdfname` | `UNIQUE (user_id, pdf_name)` | File names are unique per user, not globally |
| `idx_papers_user_hash` | `UNIQUE (user_id, content_hash) WHERE content_hash IS NOT NULL` | Per-user content de-duplication |
| `idx_papers_unsynced` | `(milvus_synced) WHERE milvus_synced = FALSE` | Fast lookup of papers needing reconciliation |
| `idx_chunks_tsv` | `GIN (tsv)`, `tsv = to_tsvector('simple', chunk_text)` | Exact-term matching (English terms, acronyms) |
| `idx_chunks_tsv_turkish` | `GIN (tsv_turkish)`, `tsv_turkish = to_tsvector('turkish', chunk_text)` | Turkish stemming (inflected word forms) |
| `idx_chat_conversations_user_updated` | `(user_id, updated_at DESC)` | Conversation sidebar ordering |
| `idx_chat_messages_conversation` | `(conversation_id, created_at)` | Ordered history retrieval |

`keywords`, `searches` and `suggestions` come from the baseline migration. No current code path writes to them.

### Milvus

Database: `MILVUS_DB`, created on startup if missing. All collections use the same index:

```python
HNSW_INDEX = {"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 200}}
# search time: {"metric_type": "COSINE", "params": {"ef": 128}}
```

| Collection | Granularity | Fields |
|---|---|---|
| `liftup_titles` | 1 vector per paper | `id` (auto PK), `user_id`, `pdf_name`, `text` (≤1024), `vector` |
| `liftup_abstracts` | 1 vector per paper | `id`, `user_id`, `pdf_name`, `text` (≤4096), `vector` |
| `liftup_fulltext` | N vectors per paper | `id`, `user_id`, `pdf_name`, `chunk_idx`, `text` (≤2048), `section`, `subsection`, `page_start`, `page_end`, `vector` |

- **Vector dimension:** 768 (`EMBEDDING_DIM`).
- **Filtering:** every search and delete applies a boolean expression on `user_id`. PDF Chat adds
  `pdf_name in [...]` when documents are selected. File names are sanitized before they are used in
  expressions.
- **Schema drift:** `init_milvus.py` compares field names and vector dimension on startup. If either changed,
  it drops and recreates the collection.

---

## Search & Retrieval

| Parameter | Value | Source |
|---|---|---|
| Embedding model | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | `services/config.py` |
| Vector dimension | 768, L2-normalized (`normalize_embeddings=True`) | `services/config.py` |
| Similarity metric | COSINE | `services/database/init_milvus.py` |
| Vector index | HNSW, `M = 16`, `efConstruction = 200`, search `ef = 128` | `init_milvus.py`, `milvus_service.py` |
| Lexical search | `plainto_tsquery` against `simple` and `turkish` tsvectors, `GREATEST(ts_rank…)` | `postgres_service.py` |
| Fusion | Reciprocal Rank Fusion, `score = Σ 1 / (60 + rank)`, de-duplicated by `(pdf_name, chunk_idx)` | `services/hybrid_search.py` |
| Reranking | LLM returns a JSON permutation, first 400 characters per candidate, `temperature = 0` | `services/llm/reranker.py` |

### PDF Chat retrieval

| Setting | Value |
|---|---|
| Top-k (no PDF selected) | 8 |
| Top-k (PDFs selected) | 4 per selected PDF, capped at 24 |
| Vector score threshold | `0.35`, applied only when searching the whole library |
| Keyword hits | Not thresholded, because a match already requires a real term hit |
| Retrieval query | Last 2 stored messages + current message |
| Prompt history | Last 10 stored messages |
| Generation | `temperature = 0.4`, `max_tokens = 1600`, streamed |

The vector threshold is skipped when the user selects documents explicitly. In that case the search is already
scoped to those documents, and cross-lingual pairs, such as an English document and a Turkish question,
score well below the library-wide threshold even when the content is relevant.

### Project Suggestion retrieval

| Mode | Collection | Strategy | LLM call |
|---|---|---|---|
| `title` | `liftup_titles` | Filtered COSINE top-k (default 12) | Topic analysis (`text` mode) |
| `abstract` | `liftup_abstracts` | Filtered COSINE top-k, one hit per paper | Topic analysis (`text` mode) |
| `fulltext` | `liftup_fulltext` | Hybrid search with `top_k × 4` candidates, first-seen max-pooling per paper in RRF order, LLM rerank | RAG analysis (`rag` mode) |

In `fulltext` mode, each result carries its winning chunk plus other fused chunks from the same paper. The top
three papers also get up to four stored chunks from PostgreSQL. The LLM receives the uploaded project text
(capped at 16,000 characters) and up to 2,500 characters of evidence per similar paper, and returns structured
JSON (`temperature = 0.75`).

---

## Project Structure

```text
.
├── backend/
│   ├── main.py                     # FastAPI app, CORS, router registration, /health, startup checks
│   ├── Dockerfile                  # python:3.10-slim, CPU torch, embedding model baked into the image
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── migrations/versions/        # Baseline, users, per-user scoping, chat, FTS, section metadata, token_version
│   ├── routers/
│   │   ├── auth_router.py          # /auth: register, login, logout, me, profile, change-password
│   │   ├── database_router.py      # /db: upload and index, list, detail, preview, remove, stats, reconcile, reset
│   │   ├── chat_router.py          # /chat: message, SSE stream, conversation CRUD
│   │   ├── suggest_router.py       # /suggest: title / abstract / fulltext search, health
│   │   └── pdf_router.py           # /pdf: split, preview-section, download-section
│   ├── services/
│   │   ├── config.py               # Single source of environment-driven settings
│   │   ├── auth.py, security.py    # Session dependencies, JWT, bcrypt
│   │   ├── rate_limit.py           # Per-IP and per-user (daily LLM) limiters
│   │   ├── upload_validation.py    # Size and PDF magic-byte checks
│   │   ├── text_preprocessing.py   # PyMuPDF extraction, heading and page markers
│   │   ├── chunking_service.py     # Sentence-aware, section-bounded chunking
│   │   ├── hybrid_search.py        # Reciprocal Rank Fusion
│   │   ├── chat_service.py         # PDF Chat RAG orchestration and streaming
│   │   ├── suggest_service.py      # Project Suggestion pipelines
│   │   ├── pdf_splitter.py         # Font-size based proceedings splitter
│   │   ├── database/
│   │   │   ├── postgres_service.py # asyncpg pool and queries
│   │   │   ├── milvus_service.py   # Insert, search, delete, stats
│   │   │   └── init_milvus.py      # Database and collection bootstrap
│   │   └── llm/
│   │       ├── openrouter_client.py      # Shared client: retry, backoff, streaming
│   │       ├── chat_llm_service.py       # Chat completion parameters
│   │       ├── llm_suggestion_service.py # Suggestion prompts and JSON parsing
│   │       └── reranker.py               # LLM-based reranking
│   └── scripts/
│       ├── reembed_all.py          # Re-embed stored chunks after an embedding model change
│       └── rechunk_all.py          # Re-chunk and re-embed after a chunking logic change
├── frontend/
│   ├── Dockerfile                  # node:24-slim build, nginx runtime, VITE_API_URL=/api
│   ├── nginx.conf                  # SPA fallback routing
│   ├── services/service.js         # API client (axios + fetch-based SSE reader)
│   └── src/
│       ├── App.jsx                 # Routes, protected by ProtectedRoute
│       ├── AuthContext.jsx         # Session state from /auth/me
│       └── pages/                  # Auth, Home, PdfSplitter, Suggest, Chat, Database, Settings, Help
├── deploy/
│   ├── docker-compose.yml          # etcd, minio, milvus, postgres, backend, frontend, nginx
│   ├── .env.example                # Deployment secrets template
│   └── nginx/                      # HTTP and HTTPS reverse-proxy templates
└── docs/
    ├── architecture.svg
    ├── rag-pipeline.svg
    └── deploy/gcp-vm-setup.md      # VM provisioning and TLS runbook
```

---

## Security

| Area | Implementation |
|---|---|
| **Password storage** | bcrypt with per-hash salt. Passwords must be 8–72 bytes and contain a letter and a digit (the 72-byte cap matches bcrypt's input limit). |
| **Sessions** | HS256 JWT in an `httpOnly`, `SameSite=Lax` cookie (`Secure` in production). Default lifetime is 7 days. The backend refuses to start without `JWT_SECRET`. |
| **Session revocation** | Each token carries `token_version` and is checked against the database on every request. A password change increments the version, invalidating all other sessions. |
| **Authorization** | Every router except `/auth` requires a valid session. `reconcile` and `reset` also require the `admin` role, granted only to emails listed in `ADMIN_EMAILS` at registration, or a constant-time-compared `X-API-Key`. |
| **Tenant isolation** | `user_id` comes only from the verified JWT and is applied in every PostgreSQL query, Milvus filter expression and storage path. |
| **Login hardening** | Identical error for unknown email and wrong password. Disabled accounts (`is_active = FALSE`) cannot log in. |
| **Input validation** | Pydantic models (`EmailStr`, E.164 phone normalization, message length ≤ 4000). PDF magic-byte and size checks. `Path(...).name` for file paths. Quote stripping for Milvus expressions. |
| **Rate limiting** | Sliding-window limits per client IP: 20/min on upload, split, chat and suggestion endpoints, 10/min on auth endpoints. A separate per-user quota on LLM endpoints (default 5 per rolling 24 hours). |
| **Proxy trust** | nginx overwrites `X-Forwarded-For` with `$remote_addr`. The backend port is not published, so only nginx can reach it. |
| **Surface reduction** | `/docs`, `/redoc` and `/openapi.json` are disabled unless `ENABLE_DOCS=true`. CORS is restricted to configured origins. |
| **Secrets** | All secrets come from environment variables. `.env` files are git-ignored, and only `.env.example` templates are committed. |

---

## Deployment

**Live application:** [https://altayai.duckdns.org/](https://altayai.duckdns.org/)

The production stack is defined in `deploy/docker-compose.yml` and runs on a Google Cloud Compute Engine VM.

| Service | Image / build | Role |
|---|---|---|
| `nginx` | `nginx:1.27-alpine` | Public entry point on ports 80 and 443. TLS with Let's Encrypt certificates. |
| `frontend` | `../frontend` | Static React build served by nginx |
| `backend` | `../backend` | FastAPI on Uvicorn with `--proxy-headers`. Container health check on `/health`. |
| `postgres` | `postgres:16-alpine` | Relational store (`postgres_data` volume) |
| `milvus` | `milvusdb/milvus:v2.4.15` | Vector store, standalone mode (`milvus_data` volume) |
| `etcd` | `quay.io/coreos/etcd:v3.5.16` | Milvus metadata |
| `minio` | `milvusdb/minio` | Milvus object storage |

Additional details:

- **Secrets and domain values** come from `deploy/.env`: `POSTGRES_*`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`,
  `JWT_SECRET`, `ADMIN_EMAILS`, `ADMIN_API_KEY`, `PUBLIC_ORIGIN` and `PUBLIC_DOMAIN`. Non-secret production
  settings are pinned in the compose file, for example `COOKIE_SECURE=true`, `ENABLE_DOCS=false` and the
  rate limits.
- **nginx templates.** `deploy/nginx/default.conf.template` is the HTTP variant. After certificates are issued,
  it is replaced with `nginx-https.conf.template`, which adds the HTTPS server and the HTTP→HTTPS redirect.
- **Health.** `GET /api/health` checks PostgreSQL and Milvus connectivity and returns `ok` or `degraded`.
- **Runbook.** VM provisioning, Docker installation, TLS issuance and renewal are documented in
  [`docs/deploy/gcp-vm-setup.md`](docs/deploy/gcp-vm-setup.md).

---

## Installation & Local Development

### Option A: Docker Compose (full stack)

Requirements: Docker with the Compose plugin and an [OpenRouter API key](https://openrouter.ai/keys).

```bash
git clone https://github.com/rmmehmet/semantic_similarity_recommender.git
cd semantic_similarity_recommender/deploy

cp .env.example .env
# Fill in POSTGRES_PASSWORD, JWT_SECRET, OPENROUTER_API_KEY, ADMIN_EMAILS,
# PUBLIC_ORIGIN (e.g. http://localhost) and PUBLIC_DOMAIN (e.g. localhost)

docker compose build
docker compose up -d postgres milvus etcd minio
docker compose run --rm backend alembic upgrade head
docker compose up -d
```

With the default HTTP nginx template, the application is served on `http://<host>/`. The compose file sets
`COOKIE_SECURE=true`, and browsers only send secure cookies over HTTPS (with an exception for `localhost` in
most browsers). Plain-HTTP access from another host therefore needs TLS or a local override of that value.

Generate a JWT secret with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Option B: Local development

Requirements: Python 3.10, Node.js, PostgreSQL 16, a running
[Milvus 2.4 standalone](https://milvus.io/docs/install_standalone-docker.md) instance and an OpenRouter API key.

**1. Backend**

```bash
cd backend
python -m venv ../venv
source ../venv/bin/activate        # Windows: ..\venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # set DATABASE_URL, JWT_SECRET, OPENROUTER_API_KEY, ADMIN_EMAILS
```

**2. Database**

```bash
createdb liftup_db                 # or the database named in DATABASE_URL
alembic upgrade head
```

You do not need to create the Milvus database or collections yourself. The backend creates them on startup.

**3. Run the API**

The app forces `HF_HUB_OFFLINE=1` by default. On the first run, allow the embedding model to download once:

```bash
HF_HUB_OFFLINE=0 uvicorn main:app --reload --port 8000   # first run only
uvicorn main:app --reload --port 8000
```

With `ENABLE_DOCS=true` (the `.env.example` default), interactive API docs are available at
`http://localhost:8000/docs`.

**4. Frontend**

```bash
cd frontend
cp .env.example .env               # VITE_API_URL=http://localhost:8000
npm install
npm run dev                        # http://localhost:5173
```

### Environment variables (backend)

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | yes | none | PostgreSQL connection string |
| `JWT_SECRET` | yes | none | JWT signing key. The app will not start without it. |
| `OPENROUTER_API_KEY` | for LLM features | none | OpenRouter key. LLM features are disabled if unset. |
| `OPENROUTER_MODEL` | no | `meta-llama/llama-3.1-8b-instruct` | Generation model |
| `RERANK_MODEL` | no | `OPENROUTER_MODEL` | Reranking model |
| `OPENROUTER_BASE_URL` | no | `https://openrouter.ai/api/v1` | API base URL |
| `MILVUS_HOST` / `MILVUS_PORT` / `MILVUS_DB` | no | `localhost` / `19530` / `liftup_db` | Milvus connection |
| `EMBEDDING_MODEL` / `EMBEDDING_DIM` | no | `paraphrase-multilingual-mpnet-base-v2` / `768` | Embedding model. Changing it requires `scripts/reembed_all.py`. |
| `CORS_ORIGINS` | no | `http://localhost:5173,http://127.0.0.1:5173` | Allowed origins |
| `ADMIN_EMAILS` | no | empty | Emails granted `admin` at registration |
| `ADMIN_API_KEY` | no | empty | Optional service key for admin endpoints |
| `COOKIE_SECURE` | no | `false` | Set `true` behind HTTPS |
| `JWT_EXPIRE_MINUTES` | no | `10080` | Session lifetime |
| `MAX_UPLOAD_MB` | no | `30` | Upload size limit |
| `RATE_LIMIT_PER_MINUTE` / `AUTH_RATE_LIMIT_PER_MINUTE` | no | `20` / `10` | Per-IP limits |
| `LLM_DAILY_LIMIT_PER_USER` | no | `5` | Per-user LLM calls per rolling 24 hours |
| `ENABLE_DOCS` | no | `false` | Expose OpenAPI docs |
| `PDF_STORAGE_DIR` | no | `storage/pdfs` | Uploaded PDF directory |
| `HF_HUB_OFFLINE` | no | `1` | Set `0` to allow model downloads |

### Changing the embedding model

Vectors from different models are not comparable. After changing `EMBEDDING_MODEL` or `EMBEDDING_DIM`, run:

```bash
cd backend
python scripts/reembed_all.py
```

The script re-embeds every user's stored chunks from PostgreSQL and rewrites them to Milvus. Collections are
recreated when the vector dimension changes. PDFs do not need to be uploaded again. For the Docker image, also update the `EMBEDDING_MODEL` build argument in
`backend/Dockerfile`. After a chunking logic change, use `scripts/rechunk_all.py` instead.

---

## API Overview

All routes are relative to the API root (`/api` behind nginx). Every route except `/auth/register`,
`/auth/login`, `/auth/logout` and `/health` requires a session cookie.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Create an account and start a session |
| `POST` | `/auth/login` | Start a session (sets `altayai_token` cookie) |
| `GET` / `PATCH` | `/auth/me` | Current user / update profile |
| `POST` | `/auth/change-password` | Change password and revoke other sessions |
| `POST` | `/db/add` | Upload, extract, chunk, embed and index a PDF |
| `GET` | `/db/list` · `/db/detail/{pdf_name}` · `/db/preview/{pdf_name}` | Library listing, details with chunks, inline PDF stream |
| `DELETE` | `/db/remove/{pdf_name}` | Remove a paper from PostgreSQL, Milvus and disk |
| `POST` | `/db/reconcile` *(admin)* | Repair PostgreSQL / Milvus drift for all users |
| `POST` | `/chat/message/stream` | RAG chat answer as an SSE stream (`chunk`, `done`, `error`) |
| `POST` | `/chat/message` | Same pipeline, non-streaming |
| `GET` / `DELETE` | `/chat/conversations[/{id}]` | List, load or delete conversations |
| `POST` | `/suggest/search` | `title` / `abstract` / `fulltext` similarity search with LLM analysis |
| `POST` | `/pdf/split` | Split a proceedings PDF by font-size threshold |
| `GET` | `/health` | PostgreSQL and Milvus health |

**Chat stream example**

```http
POST /api/chat/message/stream
Content-Type: application/json

{ "message": "Bu projede hangi veri seti kullanılmış?", "pdf_names": ["paper.pdf"], "conversation_id": null }
```

```text
event: chunk
data: {"delta": "Projede ..."}

event: done
data: {"conversation_id": 42, "sources": [{"pdf_name": "paper.pdf", "raw_title": "...", "score": 0.61, "section": "3. Yöntem"}], "title": "..."}
```

---

## Engineering Decisions

**Separate relational and vector stores.**
PostgreSQL stores the authoritative text and metadata. Milvus stores vectors for approximate nearest-neighbour
search. Because all chunk text lives in PostgreSQL, the vector index can be rebuilt at any time
(`reconcile`, `reembed_all.py`, `rechunk_all.py`) without the original PDFs.

**Explicit sync state between stores.**
Papers are written to PostgreSQL with `milvus_synced = FALSE` and marked synced only after all Milvus writes
and flushes succeed. Startup reports unsynced papers. The admin `reconcile` endpoint re-embeds them and
deletes orphaned vectors.

**Hybrid retrieval with rank-based fusion.**
Cosine similarity and `ts_rank` are on incompatible scales, so the results are merged by rank (RRF) instead of
normalized scores. Lexical search catches exact terms, acronyms and names that dense retrieval can miss.
Two tsvector configurations are indexed because academic text mixes Turkish and English: `simple` for exact
terms and `turkish` for stemmed forms.

**Fusion order is preserved through pooling.**
In `fulltext` suggestion mode, papers are pooled by first appearance in RRF order instead of by maximum
cosine score. Keyword-only hits have no cosine score and would otherwise always lose.

**Structure-aware chunking.**
Chunks are built from whole sentences, never span two sections, and carry section and page metadata. This
metadata appears in the LLM context and in citations. Bibliography sentences are excluded because shared
references are not evidence of content similarity.

**Best-effort reranking and retrieval.**
OpenRouter has no dedicated rerank endpoint, so reranking is a constrained chat completion that must return a
complete index permutation. Any parsing or network failure falls back to the fused order. Vector and keyword
searches also fail independently.

**One LLM client for all features.**
All LLM traffic goes through `openrouter_client.py`. It handles request building, retries on 429, 5xx and
network errors with backoff, and streaming. Generation and rerank models are separate settings.

**Server-side conversation state.**
Chat history is loaded from PostgreSQL on every request instead of being sent by the client. Conversations are
created lazily and deleted again if the first message fails.

**Same-origin deployment.**
The frontend is built with `VITE_API_URL=/api`, and nginx proxies that path to the backend. The `SameSite=Lax`
session cookie therefore works without cross-origin cookie configuration.

**Reproducible model runtime.**
The embedding model is downloaded during the Docker build and loaded offline at runtime
(`HF_HUB_OFFLINE=1`). A CPU-only PyTorch wheel keeps the image free of CUDA libraries.

---

## Limitations & Future Improvements

- **Embedding input length.** `paraphrase-multilingual-mpnet-base-v2` truncates inputs at 128 tokens, while
  full-text chunks can be up to 850 characters. Part of a long chunk may not be represented in its vector.
  A longer-context multilingual embedding model would need `reembed_all.py`.
- **In-memory rate limiting.** Rate limits and the daily LLM quota live in process memory. They reset on
  restart and are not shared across workers. Running multiple instances would need a shared store such as
  Redis.
- **Single-process compute.** Embedding runs on CPU inside the API process, so large uploads compete with chat
  requests for CPU time.
- **Reranker context.** The LLM reranker sees only the first 400 characters of each candidate.
- **No automated tests or CI.** `pytest` is listed in `requirements.txt`, but the repository has no test suite
  and no retrieval evaluation set.
- **Account verification.** Registration validates email and phone formats but does not verify ownership.
- **Unused schema and dependencies.** The `keywords`, `searches` and `suggestions` tables, and packages such as
  `scikit-learn` and `pandas`, are no longer used by the code.

---

## Author

Developed by [**rmmehmet**](https://github.com/rmmehmet) as part of the BM498 Senior Design Project.

Repository: [github.com/rmmehmet/semantic_similarity_recommender](https://github.com/rmmehmet/semantic_similarity_recommender)
