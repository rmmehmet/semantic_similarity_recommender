from __future__ import annotations

import re

# ── Türkçe kısaltmalar — bunlarda cümle sonu SAYILMAZ ────────────
_TR_ABBREVS = re.compile(
    r'\b(Dr|Prof|Doç|Yrd|Arş|Gör|Öğr|vb|vs|bkz|örn|ör|Şek|Tab|'
    r'No|no|Md|md|akt|s|sy|ss|vol|Vol|Fig|fig|ed|Ed)\.',
    re.IGNORECASE,
)


def _split_sentences(text: str) -> list[str]:
    """
    Türkçe uyumlu cümle bölücü.
    Kısaltma noktaları (Dr., vb., bkz.) cümle sonu sayılmaz.
    """
    # Kısaltma noktalarını geçici olarak maskele
    masked = _TR_ABBREVS.sub(lambda m: m.group().replace('.', '<DOT>'), text)

    # Cümle sonu: . ! ? sonrası boşluk + büyük harf veya rakam
    parts = re.split(r'(?<=[.!?])\s+', masked)

    # Maskeyi geri al, boş parçaları temizle
    return [p.replace('<DOT>', '.').strip() for p in parts if p.strip()]


# ══════════════════════════════════════════════════════════════════
# FULLTEXT CHUNKING  —  sentence-aware + cümle bazlı overlap
# ══════════════════════════════════════════════════════════════════

def chunk_fulltext(
    text: str,
    size: int         = 850,
    overlap_sentences: int = 1,   # karakter değil, cümle sayısı
) -> list[str]:
    """
    Sentence-aware chunking with sentence-level overlap.

    Değişiklikler (önceki versiyona göre):
    - Karakter bazlı overlap yerine cümle bazlı overlap
      → Yarım cümle taşıma sorunu ortadan kalktı
    - Türkçe kısaltmalar artık cümle sonu sayılmıyor
    """
    text = text.strip()
    if not text:
        return []

    sentences = _split_sentences(text)
    chunks:   list[str]      = []
    current:  list[str]      = []   # cümle listesi (string değil)
    cur_len:  int            = 0

    for sent in sentences:
        sent_len = len(sent)

        if cur_len + sent_len + 1 > size and cur_len > 0:
            # Mevcut chunk'ı kaydet
            chunks.append(" ".join(current))

            # Cümle bazlı overlap: son N cümleyi tut
            current = current[-overlap_sentences:] if overlap_sentences else []
            cur_len = sum(len(s) + 1 for s in current)

        # Tek cümle size'ı aşıyorsa direkt ekle (bölme yapma)
        current.append(sent)
        cur_len += sent_len + 1

    if current:
        chunks.append(" ".join(current))

    return chunks


# ══════════════════════════════════════════════════════════════════
# ABSTRACT CHUNKING
# ══════════════════════════════════════════════════════════════════

def chunk_abstract(abstract: str, max_len: int = 500) -> list[str]:
    """
    Abstract için tek parça temsil.
    max_len aşılırsa son uygun cümle sınırında keser.
    Overlap uygulanmaz (tek chunk).
    """
    abstract = abstract.strip()
    if not abstract:
        return []

    if len(abstract) <= max_len:
        return [abstract]

    # Son cümle sınırını bul
    cut = abstract[:max_len]
    last_end = max(
        cut.rfind(". "),
        cut.rfind("! "),
        cut.rfind("? "),
    )
    if last_end > 100:
        cut = abstract[:last_end + 1].strip()

    return [cut]


# ══════════════════════════════════════════════════════════════════
# CHUNK RECORDS BUILDER
# ══════════════════════════════════════════════════════════════════

def build_chunk_records(
    title:    str,
    abstract: str,
    fulltext: str,
) -> tuple[list[dict], list[str], list[str]]:
    """
    title    → chunk yapılmaz, direkt kayıt
    abstract → chunk_abstract()
    fulltext → chunk_fulltext()

    Döner: (records, ft_chunks, abs_chunks)
    """
    records: list[dict] = []

    # Başlık — tek kayıt, chunk yok
    if title:
        records.append({"chunk_text": title, "chunk_idx": 0, "chunk_type": "title"})

    # Özet
    abs_chunks = chunk_abstract(abstract)
    for i, ch in enumerate(abs_chunks):
        records.append({"chunk_text": ch, "chunk_idx": i, "chunk_type": "abstract"})

    # Tam metin
    ft_chunks = chunk_fulltext(fulltext)
    for i, ch in enumerate(ft_chunks):
        records.append({"chunk_text": ch, "chunk_idx": i, "chunk_type": "fulltext"})

    return records, ft_chunks, abs_chunks