"""
chunking_service.py
-------------------
Chunk işlemlerinin tek sorumlu olduğu servis.
database_router.py bu modülü import eder.

Kural (README):
  - Title   : chunk yapılmaz, tek parça
  - Abstract: 300-500 karakter, overlap yok
  - Fulltext: 700-1000 karakter, overlap var (sentence-aware)
"""

from __future__ import annotations

import re


# ══════════════════════════════════════════════════════════════════
# SENTENCE-AWARE CHUNKING  (fulltext için)
# ══════════════════════════════════════════════════════════════════

def chunk_fulltext(
    text: str,
    size: int    = 850,
    overlap: int = 100,
) -> list[str]:
    """
    Sentence-aware chunking — fulltext için.

    Adımlar:
      1. Metni cümlelere böl (.  !  ? sonrası boşluk).
      2. Cümleleri 'size' sınırına kadar birleştir.
      3. Yeni chunk başlarken önceki chunk'ın son 'overlap' karakterini
         önek olarak ekle (context sürekliliği için).
      4. Tek cümle 'size'ı aşıyorsa hard-cut yapılır.

    Args:
        text   : Ham tam metin.
        size   : Hedef max karakter sayısı (varsayılan 850).
        overlap: Chunk'lar arası örtüşme karakteri (varsayılan 100).

    Returns:
        Chunk string listesi. Boş metin → [].
    """
    text = text.strip()
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current            = ""

    for sent in sentences:
        # Mevcut chunk'a sığıyor mu?
        candidate = (current + " " + sent).strip() if current else sent

        if len(candidate) <= size:
            current = candidate
        else:
            # Mevcut chunk'ı kaydet
            if current:
                chunks.append(current)

            # Overlap: önceki chunk'ın son 'overlap' karakteri
            tail = current[-overlap:] if current and overlap > 0 else ""

            # tail + yeni cümle hâlâ sığıyor mu?
            new_start = (tail + " " + sent).strip() if tail else sent

            if len(new_start) <= size:
                current = new_start
            else:
                # Çok uzun cümle → hard-cut
                current = sent[:size]

    if current:
        chunks.append(current)

    return chunks


# ══════════════════════════════════════════════════════════════════
# ABSTRACT CHUNKING  (tek parça, 300-500 karakter sınırı)
# ══════════════════════════════════════════════════════════════════

def chunk_abstract(abstract: str, max_len: int = 500) -> list[str]:
    """
    Abstract chunk yapılmaz — tek parça olarak tutulur.
    max_len'i aşarsa cümle sınırından kesilir, geri kalanı atılır.

    Returns:
        Tek elemanlı liste ya da boş liste.
    """
    abstract = abstract.strip()
    if not abstract:
        return []

    if len(abstract) <= max_len:
        return [abstract]

    # max_len içinde son cümle sonu bul
    cut = abstract[:max_len]
    last_end = max(
        cut.rfind(". "),
        cut.rfind("! "),
        cut.rfind("? "),
    )
    if last_end > 100:
        cut = abstract[: last_end + 1].strip()

    return [cut]


# ══════════════════════════════════════════════════════════════════
# YARDIMCI: tüm chunk kayıtlarını üret
# ══════════════════════════════════════════════════════════════════

def build_chunk_records(
    title: str,
    abstract: str,
    fulltext: str,
) -> tuple[list[dict], list[str], list[str]]:
    """
    PostgreSQL chunks tablosu için kayıt listesi üretir.

    Returns:
        chunk_records : [{"chunk_text", "chunk_idx", "chunk_type"}, ...]
        ft_chunks     : fulltext chunk string listesi (vektörleme için)
        abs_chunks    : abstract chunk string listesi (vektörleme için)

    Kullanım:
        chunk_records, ft_chunks, abs_chunks = build_chunk_records(title, abstract, fulltext)
    """
    records: list[dict] = []

    # ── Title (chunk yapılmaz) ─────────────────────────────────
    if title:
        records.append(
            {"chunk_text": title, "chunk_idx": 0, "chunk_type": "title"}
        )

    # ── Abstract ──────────────────────────────────────────────
    abs_chunks = chunk_abstract(abstract)
    for i, ch in enumerate(abs_chunks):
        records.append(
            {"chunk_text": ch, "chunk_idx": i, "chunk_type": "abstract"}
        )

    # ── Fulltext ──────────────────────────────────────────────
    ft_chunks = chunk_fulltext(fulltext)
    for i, ch in enumerate(ft_chunks):
        records.append(
            {"chunk_text": ch, "chunk_idx": i, "chunk_type": "fulltext"}
        )

    return records, ft_chunks, abs_chunks