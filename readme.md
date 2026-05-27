<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
  <img src="https://img.shields.io/badge/React-18.3-61DAFB?style=for-the-badge&logo=react&logoColor=black"/>
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white"/>
  <img src="https://img.shields.io/badge/Milvus-2.4-00A1EA?style=for-the-badge&logo=milvus&logoColor=white"/>
  <img src="https://img.shields.io/badge/Ollama-Llama_3.1_Q4-FF6B35?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/sentence--transformers-3.0-FF9900?style=for-the-badge"/>
</p>

<h1 align="center">AltayAI — Academic Similarity & Project Suggestion System</h1>

<p align="center">
  A RAG-powered academic decision support platform that performs multi-modal similarity analysis,<br/>
  automated paper extraction from PDFs, and LLM-driven originality assessment with topic suggestions.
</p>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Database Schemas](#database-schemas)
  - [PostgreSQL](#postgresql-schema)
  - [Milvus Collections](#milvus-collections)
- [Similarity Engine](#similarity-engine)
- [PDF Splitter](#pdf-splitter)
- [RAG Pipeline](#rag-pipeline)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [API Reference](#api-reference)
- [Environment Variables](#environment-variables)

---

## Overview

**AltayAI** is an end-to-end academic intelligence platform built for university-level project evaluation. It enables students and faculty to:

- Detect semantic similarity between academic papers using multiple NLP methods
- Split multi-paper PDFs into individual proceedings based on configurable thresholds
- Query a vector database for similar works across title, abstract, and full-text dimensions
- Receive LLM-generated originality analyses, improvement suggestions, and alternative topic proposals

The system goes beyond raw similarity scores — it **explains why** two documents are similar, **highlights** what is unique, and **proposes** genuinely novel research directions.

---

## Features

| Module | Description |
|---|---|
| **PDF Splitter** | Threshold-based proceeding extraction from multi-paper PDF bundles |
| **Similarity Search** | Multi-method similarity: Jaccard, TF-IDF, Cosine, Sentence-BERT |
| **Project Suggestion** | Three-mode semantic search (title / abstract / full-text) |
| **RAG Analysis** | Retrieval-Augmented Generation with chunk-level context building |
| **LLM Suggestions** | Llama 3.1 Q4 via Ollama — local, GPU-accelerated, no API key required |
| **Database Manager** | Full CRUD for papers, chunks, keywords; Milvus + PostgreSQL sync |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                           │
│   PdfSplitter │ Similarity │ Suggest │ Database                 │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / multipart-form-data
┌────────────────────────────▼────────────────────────────────────┐
│                      FastAPI Backend                            │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ pdf_router   │  │similarity_   │  │   suggest_router      │  │
│  │              │  │router        │  │                       │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬────────────┘  │
│         │                 │                     │               │
│  ┌──────▼─────────────────▼─────────────────────▼────────────┐  │
│  │                    Services Layer                         │  │
│  │                                                           │  │
│  │  text_preprocessing  │  chunking_service                 │  │
│  │  suggest_service     │  comparison_service               │  │
│  │  highlight_service   │  llm_suggestion_service           │  │
│  └──────┬───────────────────────────────────┬───────────────┘  │
│         │                                   │               │
│  ┌──────▼──────────┐            ┌───────────▼─────────────┐  │
│  │   PostgreSQL    │            │         Milvus          │  │
│  │  papers/chunks  │            │  liftup_titles          │  │
│  │  keywords       │            │  liftup_abstracts       │  │
│  │  searches       │            │  liftup_fulltext        │  │
│  │  suggestions    │            │  (HNSW · COSINE · 384d) │  │
│  └─────────────────┘            └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │     Ollama (local)          │
              │  llama3.1:8b-instruct-q4_K_M│
              │  GPU-accelerated (num_gpu=99)│
              └─────────────────────────────┘
```

---

## Technology Stack

### Backend

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | 0.111.x | Async REST API framework |
| `uvicorn` | 0.30.x | ASGI server |
| `asyncpg` | 0.29.x | Async PostgreSQL driver |
| `pymilvus` | 2.4.x | Milvus vector database client |
| `sentence-transformers` | 3.0.x | `paraphrase-multilingual-MiniLM-L12-v2` embedding |
| `pymupdf` (fitz) | 1.24.x | PDF text extraction |
| `scikit-learn` | 1.5.x | TF-IDF vectorization |
| `python-multipart` | 0.0.9 | File upload support |
| `httpx` | 0.27.x | Async HTTP client |
| `pydantic` | 2.7.x | Data validation |

### Frontend

| Package | Version | Purpose |
|---|---|---|
| `react` | 18.3.x | UI framework |
| `react-router-dom` | 6.x | Client-side routing |
| `vite` | 5.x | Build tool |

### Infrastructure

| Component | Version | Purpose |
|---|---|---|
| PostgreSQL | 16 | Relational metadata & full text storage |
| Milvus | 2.4 | Vector similarity search (HNSW index) |
| Ollama | latest | Local LLM inference server |
| Llama 3.1 | 8B-instruct-Q4_K_M | Quantized LLM for academic analysis |

---

## Database Schemas

### PostgreSQL Schema

#### `papers` — Core paper metadata and raw text

```sql
CREATE TABLE papers (
    id          SERIAL      PRIMARY KEY,
    pdf_name    TEXT        UNIQUE NOT NULL,
    raw_title   TEXT,
    abstract    TEXT,
    fulltext    TEXT,
    book_name   TEXT        DEFAULT '',
    year        INTEGER     DEFAULT 0,
    created_at  TIMESTAMP   DEFAULT NOW(),
    updated_at  TIMESTAMP   DEFAULT NOW()
);
```

#### `chunks` — Sentence-aware text chunks

```sql
CREATE TABLE chunks (
    id          SERIAL      PRIMARY KEY,
    paper_id    INTEGER     NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    chunk_text  TEXT        NOT NULL,
    chunk_idx   INTEGER     NOT NULL,
    chunk_type  TEXT        NOT NULL DEFAULT 'fulltext'
                            CHECK (chunk_type IN ('title', 'abstract', 'fulltext'))
);
```

Chunking rules per type:

| Type | Strategy | Target Size |
|---|---|---|
| `title` | No chunking — stored as-is | — |
| `abstract` | Sentence-aware, sentence boundary preserved | ≤ 500 chars |
| `fulltext` | Sentence-aware with overlap | 850 chars, 100 overlap |

#### `keywords` — Extracted keywords per paper

```sql
CREATE TABLE keywords (
    id          SERIAL      PRIMARY KEY,
    paper_id    INTEGER     NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    keyword     TEXT        NOT NULL
);
```

#### `searches` — Query audit log

```sql
CREATE TABLE searches (
    id          SERIAL      PRIMARY KEY,
    query_text  TEXT        NOT NULL,
    searched_at TIMESTAMP   DEFAULT NOW()
);
```

#### `suggestions` — LLM-generated suggestion records

```sql
CREATE TABLE suggestions (
    id                      SERIAL      PRIMARY KEY,
    paper_id                INTEGER     REFERENCES papers(id) ON DELETE SET NULL,
    similarity_analysis     TEXT,
    original_aspects        TEXT,
    improvement_suggestions TEXT,
    topic_suggestions       TEXT,
    revised_title           TEXT,
    risk_level              TEXT,
    created_at              TIMESTAMP   DEFAULT NOW()
);
```

#### Indexes

```sql
CREATE INDEX idx_papers_pdf_name    ON papers(pdf_name);
CREATE INDEX idx_chunks_paper_id    ON chunks(paper_id);
CREATE INDEX idx_chunks_type_paper  ON chunks(paper_id, chunk_type);
CREATE INDEX idx_papers_year        ON papers(year) WHERE year > 0;
CREATE INDEX idx_keywords_paper_id  ON keywords(paper_id);
CREATE INDEX idx_suggestions_paper  ON suggestions(paper_id);
```

---

### Milvus Collections

All collections use **HNSW** index with **COSINE** metric and **384-dimensional** vectors from `paraphrase-multilingual-MiniLM-L12-v2`.

#### `liftup_titles` — One vector per paper (title embedding)

| Field | Type | Description |
|---|---|---|
| `id` | INT64 (PK, auto) | Primary key |
| `pdf_name` | VARCHAR(512) | Source PDF filename |
| `text` | VARCHAR(1024) | Paper title |
| `vector` | FLOAT_VECTOR(384) | Title embedding |

#### `liftup_abstracts` — One vector per paper (abstract embedding)

| Field | Type | Description |
|---|---|---|
| `id` | INT64 (PK, auto) | Primary key |
| `pdf_name` | VARCHAR(512) | Source PDF filename |
| `text` | VARCHAR(4096) | Abstract text (or first chunk) |
| `vector` | FLOAT_VECTOR(384) | Abstract embedding |

#### `liftup_fulltext` — N vectors per paper (chunk embeddings for RAG)

| Field | Type | Description |
|---|---|---|
| `id` | INT64 (PK, auto) | Primary key |
| `pdf_name` | VARCHAR(512) | Source PDF filename |
| `chunk_idx` | INT32 | Chunk sequence index |
| `text` | VARCHAR(2048) | Chunk text |
| `vector` | FLOAT_VECTOR(384) | Chunk embedding |

#### Index Configuration

```python
HNSW_INDEX = {
    "index_type":  "HNSW",
    "metric_type": "COSINE",
    "params": {"M": 16, "efConstruction": 200},
}
```

---

## Similarity Engine

The system implements four complementary similarity methods accessible through the **Similarity Search** module:

### 1. Jaccard Similarity

Token-level set overlap between two documents. Language-agnostic, fast, suitable for keyword-heavy comparisons.

```
Jaccard(A, B) = |A ∩ B| / |A ∪ B|
```

where A and B are sets of lowercased tokens after stopword removal.

### 2. TF-IDF Cosine Similarity

Computes term frequency–inverse document frequency vectors for both documents, then measures the cosine angle between them. Captures vocabulary importance across the corpus.

```
sim(A, B) = (TF-IDF(A) · TF-IDF(B)) / (‖TF-IDF(A)‖ · ‖TF-IDF(B)‖)
```

Implemented via `scikit-learn TfidfVectorizer` with Turkish-aware preprocessing.

### 3. Cosine Similarity (raw vectors)

Direct cosine distance between frequency or embedding vectors without IDF weighting. Used as a lightweight baseline.

### 4. Sentence-BERT Semantic Similarity

The primary method for all three suggestion modes. Uses `paraphrase-multilingual-MiniLM-L12-v2` to produce dense 384-dimensional embeddings that capture **semantic meaning** rather than lexical overlap.

```
sim(A, B) = embed(A) · embed(B)        # vectors are L2-normalized
```

Vectors are stored in Milvus and searched via HNSW approximate nearest-neighbour retrieval with `ef=128`.

**Similarity thresholds used in the suggestion system:**

| Level | Score | Behaviour |
|---|---|---|
| High | ≥ 80% | LLM suggestion is always triggered; red badge |
| Medium | 50–79% | Warning badge; LLM may suggest improvements |
| Low | < 50% | Green badge; considered sufficiently original |

---

## PDF Splitter

The PDF Splitter module automatically extracts individual academic papers from compiled proceeding PDF files (e.g., conference books containing 50+ papers in a single file).

### How It Works

1. **Page-level feature extraction** — Each page is analysed for structural signals: font size variance, blank-line density, header patterns, keyword presence (`abstract`, `introduction`, `references`, `özet`, `giriş`).
2. **Threshold scoring** — A configurable threshold (0.0–1.0) controls sensitivity. Higher values require stronger structural evidence before a page split is accepted.
3. **Boundary detection** — Pages crossing the threshold are marked as paper start boundaries.
4. **Extraction** — Each detected segment is exported as a standalone PDF file.

### Configuration

| Parameter | Default | Description |
|---|---|---|
| `threshold` | `0.5` | Split sensitivity (0 = split aggressively, 1 = rarely split) |
| `min_pages` | `2` | Minimum pages for a valid paper segment |
| `max_pages` | `40` | Maximum pages before a forced split |

### Endpoint

```
POST /split/pdf
Content-Type: multipart/form-data

file      : PDF file (required)
threshold : float 0.0–1.0 (default 0.5)
```

Returns a ZIP archive containing individual paper PDFs, each named by detected title or page range.

---

## RAG Pipeline

The Retrieval-Augmented Generation pipeline is activated when a user uploads a PDF or enters full-text in the suggestion module.

```
User PDF / Full Text
        │
        ▼
  BERT Embedding
  (paraphrase-multilingual-MiniLM-L12-v2)
        │
        ▼
  Milvus HNSW Search
  (liftup_fulltext — chunk level, top_k × 4)
        │
        ▼
  Max-Pooling per Paper
  (highest chunk score represents the paper)
        │
        ▼
  PostgreSQL Enrichment
  (book_name, year, raw_title via pg_get_paper)
        │
        ▼
  RAG Context Builder
  (top matched chunks + pg chunk retrieval for top-3 papers)
        │
        ▼
  Ollama — Llama 3.1 8B Q4 (GPU)
  Prompt: pdf_full_text + matched chunks + similar titles
        │
        ▼
  Structured JSON Response
  {field, risk_level, similarity_analysis,
   original_aspects, improvement_suggestions,
   topic_suggestions, revised_title}
```

---

## Project Structure

```
BM498/
├── backend/
│   ├── main.py
│   ├── routers/
│   │   ├── database_router.py       # Paper CRUD, Milvus sync
│   │   ├── similarity_router.py     # Jaccard, TF-IDF, BERT comparison
│   │   ├── pdf_router.py            # PDF splitting
│   │   └── suggest_router.py        # Suggestion system entry point
│   └── services/
│       ├── text_preprocessing.py    # PDF text extraction (fitz)
│       ├── chunking_service.py      # Sentence-aware chunking
│       ├── comparison_service.py    # Jaccard / TF-IDF / cosine
│       ├── highlight_service.py     # Matched text highlighting
│       ├── pdf_splitter.py          # Threshold-based PDF splitting
│       ├── suggest_service.py       # Search pipeline (title/abstract/fulltext)
│       ├── database/
│       │   ├── postgres_service.py  # Async PostgreSQL CRUD
│       │   ├── milvus_service.py    # Milvus insert / search / delete
│       │   └── init_milvus.py       # Collection schema bootstrap
│       └── llm/
│           └── llm_suggestion_service.py  # Ollama / Llama 3.1 Q4
│
└── frontend/
    ├── public/
    └── src/
        ├── App.jsx
        ├── pages/
        │   ├── Home/
        │   ├── PdfSplitter/
        │   ├── Similarity/
        │   ├── Suggest/
        │   │   ├── Suggest.jsx
        │   │   └── Suggest.css
        │   └── Database/
        └── services/
            └── service.js
```

---

## Installation

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16
- [Milvus 2.4](https://milvus.io/docs/install_standalone-docker.md) (Docker recommended)
- [Ollama](https://ollama.com/download)

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/bm498-altayai.git
cd bm498-altayai
```

### 2. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

**`requirements.txt`**
```
fastapi==0.111.*
uvicorn[standard]==0.30.*
asyncpg==0.29.*
pymilvus==2.4.*
sentence-transformers==3.0.*
pymupdf==1.24.*
scikit-learn==1.5.*
python-multipart==0.0.9
httpx==0.27.*
pydantic==2.7.*
```

### 3. PostgreSQL Setup

```bash
psql -U postgres -c "CREATE DATABASE liftup_db;"
psql -U postgres -d liftup_db -f schema.sql
```

**`schema.sql`** — run the full schema from the [Database Schemas](#postgresql-schema) section above.

### 4. Milvus Setup

```bash
# Start Milvus via Docker Compose (standalone)
wget https://github.com/milvus-io/milvus/releases/download/v2.4.0/milvus-standalone-docker-compose.yml \
     -O docker-compose.yml
docker compose up -d

# Create collections
cd backend
python services/database/init_milvus.py
```

### 5. Ollama + LLM Setup

```bash
# Install Ollama (Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the model
ollama pull llama3.1:8b-instruct-q4_K_M
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

# Standard
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# With GPU-accelerated Ollama (Linux/Mac)
OLLAMA_GPU_LAYERS=99 ollama serve &
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Windows CMD
start /b cmd /c "set OLLAMA_GPU_LAYERS=99 && ollama serve"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm run dev
# Runs at http://localhost:5173
```

### Register the Suggest Router in `main.py`

```python
from fastapi import FastAPI
from routers.database_router  import router as database_router
from routers.similarity_router import router as similarity_router
from routers.pdf_router        import router as pdf_router
from routers.suggest_router    import router as suggest_router

app = FastAPI(title="AltayAI", version="1.0.0")

app.include_router(database_router,  prefix="/database")
app.include_router(similarity_router, prefix="/search")
app.include_router(pdf_router,        prefix="/split")
app.include_router(suggest_router,    prefix="/suggest")
```

---

## API Reference

### Suggestion System

#### `POST /suggest/search`

Runs the full suggestion pipeline for the selected search mode.

**Request** — `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `search_type` | `string` | ✅ | `"title"` \| `"abstract"` \| `"fulltext"` |
| `query_text` | `string` | ⚠️ | Input text (required if no file) |
| `top_k` | `integer` | ❌ | Number of results (default: `12`) |
| `file` | `File` | ⚠️ | PDF file — fulltext mode only |

**Response**

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
      "matched_text": "In this study, a U-Net based architecture..."
    }
  ],
  "llm_suggestion": {
    // text mode
    "mode": "text",
    "success": true,
    "field": "Computer Vision",
    "risk_level": "yüksek",
    "analysis": "The submitted work closely resembles...",
    "topic_suggestions": [
      { "title": "...", "rationale": "...", "novelty_score": 88 }
    ],
    "revised_title": "..."
  }
}
```

```jsonc
{
  "llm_suggestion": {
    // RAG mode (fulltext / PDF)
    "mode": "rag",
    "success": true,
    "field": "Natural Language Processing",
    "risk_level": "orta",
    "similarity_analysis": "The uploaded paper shares the transformer-based...",
    "original_aspects": ["Novel dataset construction...", "..."],
    "improvement_suggestions": ["Consider adding ablation...", "..."],
    "topic_suggestions": [...],
    "revised_title": "..."
  }
}
```

#### `GET /suggest/health`

```jsonc
{ "status": "ok", "model_ok": true, "ollama_ok": true }
```

### Database

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/database/add` | Upload and index a PDF |
| `GET` | `/database/list` | List all indexed papers |
| `GET` | `/database/detail/{pdf_name}` | Paper metadata + chunks |
| `GET` | `/database/preview/{pdf_name}` | Stream PDF for in-browser preview |
| `DELETE` | `/database/remove/{pdf_name}` | Delete from PostgreSQL + Milvus + disk |
| `GET` | `/database/stats` | Collection counts (PostgreSQL + Milvus) |
| `POST` | `/database/reset` | Full database wipe |

### Similarity

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/search/compare` | Compare two texts (Jaccard / TF-IDF / BERT) |
| `POST` | `/search/query` | Search similar papers by query text |

### PDF Splitter

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/split/pdf` | Split a multi-paper PDF by threshold |

---

## Environment Variables

Create a `.env` file in `backend/`:

```env
# PostgreSQL
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/liftup_db

# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_DB=liftup_db

# Ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=llama3.1:8b-instruct-q4_K_M
LLM_TIMEOUT_SEC=300

# Storage
PDF_STORAGE_DIR=storage/pdfs
```

Frontend `.env` (`frontend/.env`):

```env
VITE_API_URL=http://localhost:8000
```

---

## Notes

- The LLM runs **fully locally** — no OpenAI API key or internet connection is required after model download.
- GPU acceleration for Ollama is automatic on Windows with NVIDIA drivers. On Linux, set `OLLAMA_GPU_LAYERS=99` before starting `ollama serve`.
- Milvus stores only vectors. All raw text and metadata live in PostgreSQL, keeping the vector index lean.
- The suggestion system's frontend timeout is **300 seconds** to accommodate RAG + LLM processing time on consumer hardware.

---

<p align="center">
  Built for BM498 — Senior Design Project &nbsp;|&nbsp; Altay<em>AI</em>
</p>