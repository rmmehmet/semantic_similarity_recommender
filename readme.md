<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black"/>
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white"/>
  <img src="https://img.shields.io/badge/Milvus-2.4-00A1EA?style=for-the-badge&logo=milvus&logoColor=white"/>
  <img src="https://img.shields.io/badge/OpenRouter-Llama_3.1_8B-8A2BE2?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/sentence--transformers-5.4-FF9900?style=for-the-badge"/>
</p>

<h1 align="center">AltayAI — Academic Similarity, Suggestion & PDF Chat Platform</h1>

<p align="center">
  A multi-tenant, RAG-powered academic decision-support platform: split multi-paper PDF bundles,<br/>
  search your own library semantically, get LLM-driven originality analysis, and chat with your documents.
</p>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Authentication & Multi-Tenancy](#authentication--multi-tenancy)
- [Database Schemas](#database-schemas)
  - [PostgreSQL](#postgresql-schema)
  - [Milvus Collections](#milvus-collections)
- [Core Modules](#core-modules)
  - [PDF Splitter](#pdf-splitter)
  - [Project Suggestion (Similarity Engine)](#project-suggestion-similarity-engine)
  - [PDF Chat (RAG)](#pdf-chat-rag)
- [LLM Integration (OpenRouter)](#llm-integration-openrouter)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [Embedding Model Migrations](#embedding-model-migrations)
- [API Reference](#api-reference)
- [Environment Variables](#environment-variables)
- [Known Limitations](#known-limitations)

---

## Overview

**AltayAI** is an end-to-end academic intelligence platform built for university-level project evaluation. Every user has their own private PDF library — nothing is shared across accounts. It enables students and faculty to:

- Register/log in (JWT, httpOnly cookie) and manage a personal library of academic PDFs
- Split multi-paper PDF bundles into individual documents by font-size heuristics
- Search their own library semantically across title, abstract, and full-text dimensions
- Receive LLM-generated originality analyses, improvement suggestions, and alternative topic proposals for a new project idea
- Chat with their uploaded PDFs (single document, a chosen subset, or the whole library) in a persistent, ChatGPT-style conversation history

The system goes beyond raw similarity scores — it **explains why** two documents are similar, **highlights** what is unique, and **proposes** genuinely novel research directions, all grounded in the user's own documents via retrieval-augmented generation.

---

## Features

| Module | Description |
|---|---|
| **Auth** | Email/password registration & login, JWT in an httpOnly cookie, bcrypt password hashing, admin role auto-granted to configured emails |
| **PDF Splitter** | Font-size-threshold based extraction of individual papers from a multi-paper PDF bundle |
| **Project Suggestion** | Three-mode semantic search (title / abstract / full-text) over the user's own library, each producing an LLM originality assessment |
| **PDF Chat** | RAG chat over one, several, or all of the user's PDFs; conversations are persisted (Postgres) with a ChatGPT-style new-chat/history sidebar |
| **Database Manager** | Per-user PDF upload/list/preview/delete, content-hash duplicate detection, PostgreSQL ⇄ Milvus sync + admin reconcile/reset |
| **Rate Limiting** | Per-client, in-memory sliding window on the expensive (LLM/embedding) endpoints |

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                          React 19 Frontend                           │
│    Auth  │  Home  │  PdfSplitter  │  Suggest  │  Chat  │  Database   │
└────────────────────────────────┬──────────────────────────────────────┘
                                  │ HTTP (axios, withCredentials — JWT cookie)
┌────────────────────────────────▼──────────────────────────────────────┐
│                          FastAPI Backend                              │
│                                                                       │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌───────────┐ ┌──────┐ │
│  │auth_router │ │chat_router │ │database_   │ │pdf_router │ │suggest│ │
│  │/auth       │ │/chat       │ │router /db  │ │/pdf       │ │_router│ │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬─────┘ └───┬───┘ │
│        │              │              │              │           │     │
│  ┌─────▼──────────────▼──────────────▼──────────────▼───────────▼──┐ │
│  │                         Services Layer                          │ │
│  │  auth / security       │  text_preprocessing / chunking_service │ │
│  │  rate_limit             │  chat_service / suggest_service       │ │
│  │  upload_validation      │  llm/openrouter_client (+ retry)      │ │
│  └─────┬──────────────────────────────────────┬────────────────────┘ │
│        │                                      │                      │
│  ┌─────▼─────────────┐              ┌─────────▼──────────────────┐  │
│  │    PostgreSQL      │              │           Milvus            │  │
│  │  users · papers     │              │  liftup_titles              │  │
│  │  chunks              │              │  liftup_abstracts           │  │
│  │  chat_conversations  │              │  liftup_fulltext             │  │
│  │  chat_messages        │              │  (HNSW · COSINE · 768d,     │  │
│  │  (per-user scoped)    │              │   ef=128 search-time)      │  │
│  └───────────────────┘              └───────────────────────────┘  │
└──────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTPS (Bearer key)
                       ┌────────────▼─────────────┐
                       │       OpenRouter          │
                       │  meta-llama/llama-3.1-    │
                       │  8b-instruct (cloud)      │
                       └───────────────────────────┘
```

Everything user-facing is scoped by `user_id` end to end: Postgres rows carry a `user_id` column, Milvus documents carry a `user_id` scalar field used in every search/delete filter expression, and the JWT `sub` claim is the only source of identity the backend trusts.

---

## Technology Stack

### Backend

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | 0.111.x | Async REST API framework |
| `uvicorn` | 0.30.x | ASGI server |
| `asyncpg` | 0.31.x | Async PostgreSQL driver |
| `alembic` | 1.14.x | PostgreSQL schema migrations |
| `pymilvus` | 3.0.x | Milvus vector database client |
| `sentence-transformers` | 5.4.x | Embedding model runtime (`paraphrase-multilingual-mpnet-base-v2`) |
| `PyMuPDF` (fitz) | 1.27.x | PDF text/font extraction |
| `scikit-learn` | 1.7.x | Listed in `requirements.txt`; unused since the similarity-comparison feature was replaced by PDF Chat |
| `python-multipart` | 0.0.9 | File upload support |
| `httpx` / `requests` | 0.28.x / 2.34.x | HTTP clients |
| `pydantic` | 2.13.x | Data validation |
| `PyJWT` | 2.10.x | JWT issuing/verification |
| `bcrypt` | 4.2.x | Password hashing |
| `phonenumbers` | 9.0.x | Phone number validation |

### Frontend

| Package | Version | Purpose |
|---|---|---|
| `react` / `react-dom` | 19.2.x | UI framework |
| `react-router-dom` | 7.x | Client-side routing |
| `axios` | 1.16.x | HTTP client (cookie-based auth) |
| `vite` | 8.x | Build tool / dev server |

### Infrastructure

| Component | Purpose |
|---|---|
| PostgreSQL 16 | Users, paper metadata/full text, chunks, chat history |
| Milvus 2.4+ | Vector similarity search (HNSW index, per-user filtered) |
| [OpenRouter](https://openrouter.ai/) | Hosted LLM inference — `meta-llama/llama-3.1-8b-instruct` by default, model swappable via env var, no local GPU required |

> **No local LLM server is required.** Earlier versions of this project ran Llama 3.1 locally via Ollama; the LLM layer now talks to OpenRouter over HTTPS (see [LLM Integration](#llm-integration-openrouter)). The embedding model, however, still runs **locally** via `sentence-transformers` (CPU by default) — only the generative model is cloud-hosted.

---

## Authentication & Multi-Tenancy

- `POST /auth/register` — email, first/last name, phone, password + confirmation. No email/SMS verification step; only format validation (`email-validator`, `phonenumbers`) and duplicate checks.
- `POST /auth/login` — email + password → sets an httpOnly session cookie (`altayai_token`, JWT).
- `POST /auth/logout` — clears the cookie.
- `GET /auth/me` — returns the current session's user.
- Passwords are hashed with `bcrypt`. The JWT is verified on every request via a FastAPI dependency (`get_current_user`); admin-only endpoints additionally require `require_admin`.
- Accounts registering with an email listed in `ADMIN_EMAILS` (comma-separated, case-insensitive) are automatically granted the `admin` role — nobody can self-select their own role.
- `COOKIE_SECURE=false` for local `http://localhost` development; set to `true` behind HTTPS in production.

---

## Database Schemas

### PostgreSQL Schema

#### `users`

```sql
CREATE TABLE users (
    id             SERIAL      PRIMARY KEY,
    email          TEXT        NOT NULL,
    phone          TEXT        NOT NULL,
    first_name     TEXT        NOT NULL,
    last_name      TEXT        NOT NULL,
    password_hash  TEXT        NOT NULL,
    role           TEXT        NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    is_active      BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMP   DEFAULT NOW(),
    updated_at     TIMESTAMP   DEFAULT NOW()
);
-- UNIQUE (email), UNIQUE (phone)
```

#### `papers` — per-user paper metadata and raw text

```sql
CREATE TABLE papers (
    id             SERIAL      PRIMARY KEY,
    pdf_name       TEXT        NOT NULL,
    raw_title      TEXT,
    abstract       TEXT,
    fulltext       TEXT,
    book_name      TEXT        DEFAULT '',
    year           INTEGER     DEFAULT 0,
    content_hash   CHAR(64),                 -- SHA-256 of the file, for duplicate detection
    user_id        INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    milvus_synced  BOOLEAN     DEFAULT FALSE,
    created_at     TIMESTAMP   DEFAULT NOW(),
    updated_at     TIMESTAMP   DEFAULT NOW()
);
-- UNIQUE (user_id, pdf_name), UNIQUE (user_id, content_hash) WHERE content_hash IS NOT NULL
```

Two different users may upload a file with the same name or the same content — uniqueness is always scoped to `user_id`. `milvus_synced=FALSE` marks a row whose vectors may be missing/stale; `POST /db/reconcile` (admin) repairs these.

#### `chunks` — sentence-aware text chunks

```sql
CREATE TABLE chunks (
    id          SERIAL      PRIMARY KEY,
    paper_id    INTEGER     REFERENCES papers(id) ON DELETE CASCADE,
    chunk_text  TEXT        NOT NULL,
    chunk_idx   INTEGER     NOT NULL,
    chunk_type  TEXT        DEFAULT 'fulltext'   -- 'title' | 'abstract' | 'fulltext'
);
```

Chunking rules per type (`services/chunking_service.py`):

| Type | Strategy | Target Size |
|---|---|---|
| `title` | Not chunked — stored as-is | — |
| `abstract` | Sentence-aware, single chunk, cut at a sentence boundary | ≤ 500 chars |
| `fulltext` | Sentence-aware, **sentence-level** overlap (not character-level), Turkish abbreviations (`Dr.`, `vb.`, `bkz.`, …) excluded from sentence-end detection | 850 chars, 1-sentence overlap |

#### `chat_conversations` / `chat_messages` — persistent PDF Chat history

```sql
CREATE TABLE chat_conversations (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,          -- auto-generated, e.g. "15 Eyl 14:30 — dosya.pdf"
    pdf_names   JSONB NOT NULL DEFAULT '[]',   -- the PDF scope selected for this conversation
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE chat_messages (
    id              SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    sources         JSONB NOT NULL DEFAULT '[]',  -- cited pdf_name/raw_title/score per assistant reply
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

A conversation is created lazily on the **first** message (empty conversations are never persisted), and the LLM's chat history is always re-derived from `chat_messages` server-side — the client never has to (and no longer does) send its own transcript back.

#### Legacy tables (present in the schema, unused by any current code path)

`keywords`, `searches`, `suggestions` were part of an earlier iteration of the project (pre-RAG, pre-auth). They still exist (and are still cleared by `POST /db/reset`), but nothing currently writes to them — kept for backward-compatible migrations rather than active use.

#### Key indexes

```sql
CREATE UNIQUE INDEX idx_papers_user_pdfname   ON papers(user_id, pdf_name);
CREATE UNIQUE INDEX idx_papers_user_hash      ON papers(user_id, content_hash) WHERE content_hash IS NOT NULL;
CREATE INDEX        idx_papers_user_id        ON papers(user_id);
CREATE INDEX        idx_papers_unsynced       ON papers(milvus_synced) WHERE milvus_synced = FALSE;
CREATE INDEX        idx_chat_conversations_user_updated ON chat_conversations(user_id, updated_at DESC);
CREATE INDEX        idx_chat_messages_conversation       ON chat_messages(conversation_id, created_at);
```

---

### Milvus Collections

All three collections share the same index configuration and are all filtered by a `user_id` scalar field on every insert/search/delete — there is no cross-user search path anywhere in the codebase.

```python
HNSW_INDEX = {
    "index_type":  "HNSW",
    "metric_type": "COSINE",
    "params": {"M": 16, "efConstruction": 200},
}
# search-time: {"metric_type": "COSINE", "params": {"ef": 128}}
```

Vector dimension is **768** (`paraphrase-multilingual-mpnet-base-v2`) — configurable via `EMBEDDING_MODEL`/`EMBEDDING_DIM`, see [Embedding Model Migrations](#embedding-model-migrations).

#### `liftup_titles` — one vector per paper

| Field | Type | Description |
|---|---|---|
| `id` | INT64 (PK, auto) | Primary key |
| `user_id` | INT64 | Owning user |
| `pdf_name` | VARCHAR(512) | Source PDF filename |
| `text` | VARCHAR(1024) | Paper title |
| `vector` | FLOAT_VECTOR(768) | Title embedding |

#### `liftup_abstracts` — one vector per paper

| Field | Type | Description |
|---|---|---|
| `id` | INT64 (PK, auto) | Primary key |
| `user_id` | INT64 | Owning user |
| `pdf_name` | VARCHAR(512) | Source PDF filename |
| `text` | VARCHAR(4096) | Abstract text (first chunk) |
| `vector` | FLOAT_VECTOR(768) | Abstract embedding |

#### `liftup_fulltext` — N vectors per paper (chunk-level, used for both Project Suggestion's fulltext mode and PDF Chat retrieval)

| Field | Type | Description |
|---|---|---|
| `id` | INT64 (PK, auto) | Primary key |
| `user_id` | INT64 | Owning user |
| `pdf_name` | VARCHAR(512) | Source PDF filename |
| `chunk_idx` | INT32 | Chunk sequence index |
| `text` | VARCHAR(2048) | Chunk text |
| `vector` | FLOAT_VECTOR(768) | Chunk embedding |

The schema bootstrapper (`services/database/init_milvus.py`) detects **both** a field-set change and a vector-dimension change on startup — if either differs from what's expected, the collection is dropped and recreated automatically (data must then be repopulated, see below).

---

## Core Modules

### PDF Splitter

Splits a multi-paper PDF bundle (e.g., a conference proceedings file) into individual documents using a **font-size threshold**: any text span whose font size is ≥ `font_threshold` is treated as (part of) a section/paper title, and a title change marks a new section boundary.

```
POST /pdf/split          multipart/form-data: file, font_threshold (default 22.0)
POST /pdf/download-section   multipart/form-data: file, start_page, end_page, title
POST /pdf/preview-section    multipart/form-data: file, start_page, end_page
```

### Project Suggestion (Similarity Engine)

Three independent search modes, each hitting its own Milvus collection, always filtered to the current user's own documents:

| Mode | Collection | Behaviour |
|---|---|---|
| `title` | `liftup_titles` | Direct COSINE search, top-k results |
| `abstract` | `liftup_abstracts` | COSINE search, deduplicated to one hit per paper |
| `fulltext` | `liftup_fulltext` | Chunk-level search (`top_k × 4` candidates) → **max-pooling** per paper (best-scoring chunk represents the paper) → RAG analysis |

Every mode ends with an LLM call (`services/llm/llm_suggestion_service.py`) that returns structured JSON: `field`, `risk_level`, an analysis of why the input resembles existing work, concrete `topic_suggestions` with novelty scores, and a `revised_title`.

**Similarity thresholds used to select "high similarity" evidence for the LLM:**

| Level | Score | Behaviour |
|---|---|---|
| High | ≥ 80% | Always included as LLM evidence |
| Medium/Low | < 80% | Only used if fewer than 3–4 high matches exist |

### PDF Chat (RAG)

A ChatGPT-style chat interface over the user's own document library:

- **Scope**: no PDF selected → search across the user's entire library; one or more PDFs selected → search restricted to those documents only (`liftup_fulltext`, filtered by `user_id` **and** `pdf_name IN (...)`).
- **Retrieval**: the question is embedded and matched against chunk vectors; matched chunk text (not the LLM's own knowledge) is what's fed back as context, with the system prompt instructing the model to say so explicitly when the context doesn't contain an answer.
- **Persistence**: every conversation, once it has at least one message, is stored in `chat_conversations`/`chat_messages` (see schema above). The frontend keeps the active conversation id in `localStorage` and reloads it from the server on mount/remount — a page reload or component remount no longer loses the conversation.
- **History UI**: a sidebar lists past conversations (auto-titled `"<date> <time> — <first selected PDF or 'Genel Sohbet'>"`), supports switching between them (restoring both messages and the PDF scope that conversation was created with) and deleting them.

```
POST   /chat/message                     { message, pdf_names[], conversation_id? } → { reply, sources, conversation_id, title? }
GET    /chat/conversations               → { conversations: [{id, title, updated_at}] }
GET    /chat/conversations/{id}          → { id, title, pdf_names, messages[] }
DELETE /chat/conversations/{id}
```

---

## LLM Integration (OpenRouter)

All LLM calls (Project Suggestion's text/RAG analysis, and PDF Chat) go through a single shared client, `services/llm/openrouter_client.py`, hitting OpenRouter's OpenAI-compatible `/chat/completions` endpoint (`meta-llama/llama-3.1-8b-instruct` by default — any OpenRouter-hosted model can be swapped in via `OPENROUTER_MODEL`).

- **Retry with backoff**: transient failures (network errors, timeouts, HTTP 429, 5xx) are retried up to 3 times with 1s/3s backoff. Non-retryable errors (401, 400, …) fail immediately.
- **Context length guard**: in RAG mode, the uploaded PDF's full text is capped at 16,000 characters, and each cited "similar project" source is capped at 2,500 characters of actual (un-truncated) chunk evidence — bounding both cost and the risk of exceeding the model's context window.
- **RAG evidence, not UI snippets**: the LLM receives the *full* matched chunk text (deduplicated across Milvus's top hit + PostgreSQL's per-paper chunks), not the 200-character snippet shown in the UI's result cards — those are two intentionally separate fields (`rag_chunks` vs. `matched_text`).
- **No local GPU required.** The embedding model still runs locally (CPU by default), but the generative model is entirely cloud-hosted — set `OPENROUTER_API_KEY` and you're done.

---

## Project Structure

```
bm498/
├── backend/
│   ├── main.py                          # App startup, router registration, health checks
│   ├── migrations/                      # Alembic migrations (baseline → users → per-user scoping → chat)
│   ├── scripts/
│   │   └── reembed_all.py               # One-off: re-embed all users' papers after an EMBEDDING_MODEL change
│   ├── routers/
│   │   ├── auth_router.py               # /auth — register/login/logout/me
│   │   ├── chat_router.py               # /chat — PDF Chat + conversation CRUD
│   │   ├── database_router.py           # /db — paper CRUD, Postgres⇄Milvus sync, admin reconcile/reset
│   │   ├── pdf_router.py                # /pdf — font-threshold PDF splitting
│   │   └── suggest_router.py            # /suggest — title/abstract/fulltext search + health
│   └── services/
│       ├── auth.py, security.py         # JWT dependency, password hashing, token issuing
│       ├── config.py                    # ALL env-derived settings, single source of truth
│       ├── rate_limit.py                # In-memory sliding-window limiter
│       ├── upload_validation.py         # PDF magic-byte/size checks
│       ├── text_preprocessing.py        # PDF text/title/abstract extraction (fitz)
│       ├── chunking_service.py          # Sentence-aware chunking (Turkish-aware)
│       ├── pdf_splitter.py              # Font-size-threshold splitting
│       ├── suggest_service.py           # title/abstract/fulltext search pipelines
│       ├── chat_service.py              # PDF Chat RAG orchestration
│       ├── database/
│       │   ├── postgres_service.py      # Async PostgreSQL CRUD (users, papers, chunks, chat)
│       │   ├── milvus_service.py        # Milvus insert / search / delete
│       │   └── init_milvus.py           # Collection schema bootstrap (dim-change aware)
│       └── llm/
│           ├── openrouter_client.py     # Shared OpenRouter client — retry/backoff
│           ├── llm_suggestion_service.py# Project Suggestion prompts (text + RAG modes)
│           └── chat_llm_service.py      # PDF Chat prompt/response
│
└── frontend/
    ├── services/
    │   └── service.js                   # All backend API calls (axios, withCredentials)
    └── src/
        ├── App.jsx, AuthContext.jsx, ProtectedRoute.jsx
        └── pages/
            ├── Auth/                    # Login/register
            ├── Home/
            ├── PdfSplitter/
            ├── Suggest/                 # Project Suggestion UI
            ├── Chat/                    # PDF Chat UI + history sidebar
            └── Database/                # Library management
```

---

## Installation

### Prerequisites

- Python 3.10+
- Node.js 20+
- PostgreSQL 16
- [Milvus 2.4+](https://milvus.io/docs/install_standalone-docker.md) (Docker recommended)
- An [OpenRouter](https://openrouter.ai/keys) API key (no local GPU/LLM server needed)

### 1. Clone the Repository

```bash
git clone https://github.com/rmmehmet/semantic_similarity_recommender.git
cd semantic_similarity_recommender
```

### 2. Backend Setup

```bash
cd backend
python -m venv ../venv
../venv/Scripts/activate        # Linux/Mac: source ../venv/bin/activate

pip install -r requirements.txt
```

### 3. PostgreSQL Setup

```bash
psql -U postgres -c "CREATE DATABASE liftup_db;"
```

Then apply migrations (creates `users`, `papers`, `chunks`, `chat_conversations`, `chat_messages`, and legacy tables in order):

```bash
alembic upgrade head
```

### 4. Milvus Setup

```bash
# Start Milvus via Docker Compose (standalone)
wget https://github.com/milvus-io/milvus/releases/download/v2.4.0/milvus-standalone-docker-compose.yml \
     -O docker-compose.yml
docker compose up -d
```

Collections are created automatically on backend startup (`services/database/init_milvus.py`) — no separate step needed.

### 5. Configure Environment

```bash
cp backend/.env.example backend/.env
# fill in DATABASE_URL, JWT_SECRET (python -c "import secrets; print(secrets.token_hex(32))"),
# OPENROUTER_API_KEY, ADMIN_EMAILS, etc. — see Environment Variables below
```

### 6. Frontend Setup

```bash
cd frontend
npm install
```

---

## Running the Application

### Backend

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm run dev
# Runs at http://localhost:5173
```

### Production

The `--reload` dev command above runs a single worker process — fine for
development, not for production (one crash takes the whole API down, no
inbound request concurrency). Run with multiple workers behind a process
manager and a reverse proxy (nginx/Caddy) terminating TLS instead:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

Keep it alive across crashes/reboots with a process manager, e.g. systemd
or supervisor (there's no bundled unit file yet — this project doesn't
ship a Dockerfile/compose setup for the app itself, only for Milvus, see
"Milvus Setup" above). Before deploying, also set in `backend/.env`:
`COOKIE_SECURE=true`, a production `CORS_ORIGINS` (your real frontend
origin, not `localhost`), and leave `ADMIN_API_KEY`/`ENABLE_DOCS` unset
unless you specifically need them.

Router registration (already wired in `main.py`, shown here for reference):

```python
app.include_router(auth_router,     prefix="/auth")
app.include_router(database_router, prefix="/db",      dependencies=[Depends(get_current_user)])
app.include_router(chat_router,     prefix="/chat",    dependencies=[Depends(get_current_user)])
app.include_router(pdf_router,      prefix="/pdf",     dependencies=[Depends(get_current_user)])
app.include_router(suggest_router,  prefix="/suggest", dependencies=[Depends(get_current_user)])
```

---

## Embedding Model Migrations

Changing `EMBEDDING_MODEL` (or its dimension) is **not** a config-only change — every existing vector was produced by the old model and lives in an incompatible vector space. After changing the env var:

1. Restarting the backend alone is not enough — `scripts/reembed_all.py` must be run once:
   ```bash
   cd backend
   ../venv/Scripts/python.exe scripts/reembed_all.py
   ```
2. The script re-embeds every user's papers from text **already stored in PostgreSQL** (no need to re-upload PDFs), drops and recreates all three Milvus collections at the new dimension, and re-inserts everything.
3. Search/chat return empty/degraded results for the (typically short) duration of this script.

If the new model isn't in the local HuggingFace cache yet, run once with `HF_HUB_OFFLINE=0` to let it download (the app forces `HF_HUB_OFFLINE=1` by default afterward to avoid a network round-trip on every embedding call).

---

## API Reference

### Auth (`/auth`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | `{email, first_name, last_name, phone, password, password_confirm}` |
| `POST` | `/auth/login` | `{email, password}` → sets session cookie |
| `POST` | `/auth/logout` | Clears session cookie |
| `GET` | `/auth/me` | Current user info |

### Project Suggestion (`/suggest`)

#### `POST /suggest/search` — `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `search_type` | `string` | ✅ | `"title"` \| `"abstract"` \| `"fulltext"` |
| `query_text` | `string` | ⚠️ | Input text (required unless a file is given in fulltext mode) |
| `top_k` | `integer` | ❌ | Number of results (default `12`) |
| `file` | `File` | ⚠️ | PDF file — fulltext mode only |

```jsonc
{
  "success": true,
  "total": 8,
  "duration_ms": 4821,
  "results": [
    {
      "score": 0.912,
      "pdf_name": "paper_42.pdf",
      "raw_title": "Deep Learning for Medical Image Segmentation",
      "book_name": "BM498-2024",
      "year": 2024,
      "matched_text": "In this study, a U-Net based architecture..."   // short UI snippet, ≤200 chars
    }
  ],
  "llm_suggestion": {
    "mode": "rag",              // "text" for title/abstract mode
    "success": true,
    "field": "Computer Vision",
    "risk_level": "yüksek",
    "similarity_analysis": "...",
    "original_aspects": ["..."],
    "improvement_suggestions": ["..."],
    "topic_suggestions": [{ "title": "...", "rationale": "...", "novelty_score": 88 }],
    "revised_title": "..."
  }
}
```

`GET /suggest/health` → `{ "status": "ok", "model_ok": true, "openrouter_ok": true }`

### PDF Chat (`/chat`)

See [PDF Chat (RAG)](#pdf-chat-rag) above for the full endpoint list and behaviour.

### Database (`/db`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/db/add` | Upload + index a PDF (`file`, `book_name`, `year`, `force_update`) |
| `GET` | `/db/list` | List the current user's indexed papers |
| `GET` | `/db/detail/{pdf_name}` | Paper metadata + chunks |
| `GET` | `/db/preview/{pdf_name}` | Stream the stored PDF for in-browser preview |
| `DELETE` | `/db/remove/{pdf_name}` | Delete from PostgreSQL + Milvus + disk |
| `GET` | `/db/stats` | Per-user collection counts (PostgreSQL + Milvus) |
| `POST` | `/db/reconcile` | *(admin)* Repair PG⇄Milvus drift across all users |
| `POST` | `/db/reset` | *(admin)* Full data wipe (users table excluded) |

### PDF Splitter (`/pdf`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/pdf/split` | Split a multi-paper PDF by font-size threshold |
| `POST` | `/pdf/download-section` | Download a page range as a standalone PDF |
| `POST` | `/pdf/preview-section` | Preview a page range |

---

## Environment Variables

`backend/.env` (see `backend/.env.example` for the authoritative, up-to-date list):

```env
# PostgreSQL — REQUIRED, no default
DATABASE_URL=postgresql://user:password@localhost:5432/liftup_db

# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_DB=liftup_db

# Embedding model — changing this requires scripts/reembed_all.py (see above)
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
EMBEDDING_DIM=768

# OpenRouter (LLM) — https://openrouter.ai/keys — REQUIRED for LLM features
OPENROUTER_API_KEY=
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# CORS — comma-separated allowed origins (defaults to localhost:5173 if unset)
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# Optional service API key for destructive admin endpoints via automation
# (real admin access is via ADMIN_EMAILS + a logged-in session)
ADMIN_API_KEY=

# JWT sessions — REQUIRED, backend refuses to start without it
# generate with: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=
JWT_EXPIRE_MINUTES=10080

# Comma-separated emails that get the 'admin' role automatically on registration
ADMIN_EMAILS=admin@example.com

# true only behind HTTPS in production
COOKIE_SECURE=false

# Upload / rate limits
MAX_UPLOAD_MB=30
RATE_LIMIT_PER_MINUTE=20

# Disk storage for uploaded PDFs (per-user subdirectories)
PDF_STORAGE_DIR=storage/pdfs
```

`frontend/.env`:

```env
VITE_API_URL=http://localhost:8000
```

---

## Known Limitations

Tracked honestly so they're not mistaken for oversights:

- **No automated test suite / CI pipeline.** All verification is manual.
- **No token/cost usage tracking** for OpenRouter calls beyond the per-minute request rate limiter.
- **Single-process rate limiting** — the in-memory limiter does not coordinate across multiple backend workers/instances; a Redis-backed limiter would be needed for horizontal scaling.

Resolved since earlier iterations of this document:

- **Hybrid (keyword + vector) search** — `services/hybrid_search.py` combines dense retrieval with keyword matching.
- **LLM reranking** — `services/llm/reranker.py` reorders retrieved chunks before they're fed to the chat/suggestion LLM calls.
- **Section-aware chunking** — `services/chunking_service.py` tags chunks with the section they came from (including Roman-numeral and single-letter heading formats) and excludes the references/bibliography section from chunking/embedding entirely.
- **PDF Chat now streams responses** via Server-Sent Events instead of waiting for the full LLM reply.

---

<p align="center">
  Built for BM498 — Senior Design Project &nbsp;|&nbsp; Altay<em>AI</em>
</p>
