-- ══════════════════════════════════════════════════════════════════
-- migration_v2.sql
-- Mevcut veritabanına uygulanacak değişiklikler.
-- Eğer tabloları yeni oluşturuyorsanız init.sql'i kullanın.
-- ══════════════════════════════════════════════════════════════════

-- 1. papers tablosuna updated_at sütunu (postgres_service.py bunu günceller)
ALTER TABLE papers
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- 2. chunks tablosuna unique constraint YOK (kasıtlı — pg_delete_chunks önce çağrılır)
--    Eğer double-insert koruması istiyorsanız aşağıyı açın:
-- ALTER TABLE papers ADD CONSTRAINT uq_papers_pdf_name UNIQUE (pdf_name);
-- Bu constraint zaten var, sadece hatırlatma.

-- 3. Eksik index'ler
CREATE INDEX IF NOT EXISTS idx_chunks_type_paper
    ON chunks (paper_id, chunk_type);

CREATE INDEX IF NOT EXISTS idx_papers_year
    ON papers (year)
    WHERE year > 0;

-- ══════════════════════════════════════════════════════════════════
-- init.sql — Sıfırdan kurulum için
-- ══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS papers (
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

CREATE TABLE IF NOT EXISTS chunks (
    id          SERIAL      PRIMARY KEY,
    paper_id    INTEGER     NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    chunk_text  TEXT        NOT NULL,
    chunk_idx   INTEGER     NOT NULL,
    chunk_type  TEXT        NOT NULL DEFAULT 'fulltext'
                            CHECK (chunk_type IN ('title', 'abstract', 'fulltext'))
);

CREATE TABLE IF NOT EXISTS keywords (
    id          SERIAL      PRIMARY KEY,
    paper_id    INTEGER     NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    keyword     TEXT        NOT NULL
);

CREATE TABLE IF NOT EXISTS searches (
    id          SERIAL      PRIMARY KEY,
    query_text  TEXT        NOT NULL,
    searched_at TIMESTAMP   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS suggestions (
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

-- Index'ler
CREATE INDEX IF NOT EXISTS idx_papers_pdf_name     ON papers(pdf_name);
CREATE INDEX IF NOT EXISTS idx_chunks_paper_id     ON chunks(paper_id);
CREATE INDEX IF NOT EXISTS idx_chunks_type_paper   ON chunks(paper_id, chunk_type);
CREATE INDEX IF NOT EXISTS idx_papers_year         ON papers(year) WHERE year > 0;
CREATE INDEX IF NOT EXISTS idx_keywords_paper_id   ON keywords(paper_id);
CREATE INDEX IF NOT EXISTS idx_suggestions_paper   ON suggestions(paper_id);