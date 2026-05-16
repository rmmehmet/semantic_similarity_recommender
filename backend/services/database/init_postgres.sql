-- =========================================
-- DATABASE OLUŞTUR
-- =========================================

CREATE DATABASE liftup_db;

-- Sonra terminalden şu komut ile bağlan:
-- psql -U postgres -d liftup_db -f init.sql


-- =========================================
-- TABLOLAR
-- =========================================

CREATE TABLE IF NOT EXISTS papers (
    id          SERIAL PRIMARY KEY,
    pdf_name    TEXT UNIQUE NOT NULL,
    raw_title   TEXT,
    abstract    TEXT,
    fulltext    TEXT,
    book_name   TEXT,
    year        INTEGER DEFAULT 0,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chunks (
    id          SERIAL PRIMARY KEY,
    paper_id    INTEGER REFERENCES papers(id) ON DELETE CASCADE,
    chunk_text  TEXT NOT NULL,
    chunk_idx   INTEGER NOT NULL,
    chunk_type  TEXT DEFAULT 'fulltext'  -- 'title' | 'abstract' | 'fulltext'
);

CREATE TABLE IF NOT EXISTS keywords (
    id          SERIAL PRIMARY KEY,
    paper_id    INTEGER REFERENCES papers(id) ON DELETE CASCADE,
    keyword     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS searches (
    id          SERIAL PRIMARY KEY,
    query_text  TEXT NOT NULL,
    searched_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS suggestions (
    id                      SERIAL PRIMARY KEY,
    paper_id                INTEGER REFERENCES papers(id) ON DELETE SET NULL,
    similarity_analysis     TEXT,
    original_aspects        TEXT,
    improvement_suggestions TEXT,
    topic_suggestions       TEXT,
    revised_title           TEXT,
    risk_level              TEXT,
    created_at              TIMESTAMP DEFAULT NOW()
);


-- =========================================
-- INDEXLER
-- =========================================

CREATE INDEX IF NOT EXISTS idx_papers_pdf_name
ON papers(pdf_name);

CREATE INDEX IF NOT EXISTS idx_chunks_paper_id
ON chunks(paper_id);

CREATE INDEX IF NOT EXISTS idx_chunks_type
ON chunks(chunk_type);