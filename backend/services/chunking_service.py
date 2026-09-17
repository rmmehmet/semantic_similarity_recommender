from __future__ import annotations

import re

# ── Türkçe kısaltmalar — bunlarda cümle sonu SAYILMAZ ────────────
_TR_ABBREVS = re.compile(
    r'\b(Dr|Prof|Doç|Yrd|Arş|Gör|Öğr|vb|vs|bkz|örn|ör|Şek|Tab|'
    r'No|no|Md|md|akt|s|sy|ss|vol|Vol|Fig|fig|ed|Ed)\.',
    re.IGNORECASE,
)

# services/text_preprocessing.py'nin metne gömdüğü bölüm/sayfa işaretleyicileri.
_MARKER_RE = re.compile(r"<<<(SECTION|SUBSECTION|PAGE):(.*?)>>>")

# Kaynakça/Referanslar bölümündeki CÜMLELER embed edilmez (cümle seviyesinde
# filtrelenir, bkz. chunk_fulltext) — akademik benzerlik/orijinallik
# değerlendirmesinde iki projenin aynı kaynaklara atıf yapması yanıltıcı bir
# "benzerlik" sinyalidir, içerik benzerliği değildir.
_REFERENCES_SECTION_RE = re.compile(
    r"kaynak(?:ça)?|referanslar|references?|bibliography", re.IGNORECASE
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


def _tag_sentences(text: str) -> list[dict]:
    """
    <<<SECTION:..>>> / <<<SUBSECTION:..>>> / <<<PAGE:n>>> işaretleyicilerini
    ayrıştırıp her cümleyi o andaki (section, subsection, page) durumuyla
    etiketler. Döner: [{"text", "section", "subsection", "page"}, ...]
    """
    parts = _MARKER_RE.split(text)  # [önce, TİP, DEĞER, sonra, TİP, DEĞER, ...]
    tagged: list[dict] = []
    section, subsection, page = "", "", None

    def _flush(segment: str) -> None:
        for sent in _split_sentences(segment):
            tagged.append({"text": sent, "section": section, "subsection": subsection, "page": page})

    _flush(parts[0])
    i = 1
    while i + 1 < len(parts):
        mtype, mval = parts[i], parts[i + 1]
        segment = parts[i + 2] if i + 2 < len(parts) else ""
        if mtype == "SECTION":
            section, subsection = mval, ""
        elif mtype == "SUBSECTION":
            subsection = mval
        elif mtype == "PAGE":
            try:
                page = int(mval)
            except ValueError:
                pass
        _flush(segment)
        i += 3

    return tagged


# ══════════════════════════════════════════════════════════════════
# FULLTEXT CHUNKING  —  sentence-aware + cümle bazlı overlap + bölüm/sayfa
# ══════════════════════════════════════════════════════════════════

def chunk_fulltext(
    text: str,
    size: int         = 850,
    overlap_sentences: int = 1,   # karakter değil, cümle sayısı
) -> list[dict]:
    """
    Sentence-aware chunking with sentence-level overlap, section/subsection/
    page metadata dahil.

    Döner: [{"text", "section", "subsection", "page_start", "page_end"}, ...]
    section/subsection: chunk'ın İLK cümlesinin ait olduğu bölüm/alt bölüm
    (bir chunk nadiren bir bölüm sınırını geçer; geçtiğinde açılış bağlamı
    kullanılır). page_start/page_end: chunk'ı oluşturan cümlelerin kapsadığı
    sayfa aralığı — sayfa bilgisi yoksa (örn. eski/marker'sız metin) None.
    """
    text = text.strip()
    if not text:
        return []

    tagged = _tag_sentences(text)

    # Kaynakça/Referanslar bölümüne ait cümleler chunk'lara gruplanmadan ÖNCE
    # elenir (cümle seviyesinde) — chunk seviyesinde filtrelemek (eskiden
    # burada yapılıyordu) güvenilmezdi: bir chunk karakter sayısına (size)
    # göre kesildiği için kaynakça, önceki bölümle aynı chunk'a düşebiliyor
    # ve o chunk'ın section'ı hâlâ ilk cümlenin (kaynakça olmayan) bölümünü
    # taşıdığından filtre onu yakalayamıyordu — referanslar sessizce embed'e
    # sızıyordu. section VEYA subsection kaynakça ise cümle tamamen atılır.
    tagged = [
        s for s in tagged
        if not _REFERENCES_SECTION_RE.search(s["section"] or "")
        and not _REFERENCES_SECTION_RE.search(s["subsection"] or "")
    ]

    def _finalize(group: list[dict]) -> dict:
        pages = [s["page"] for s in group if s["page"] is not None]
        return {
            "text":       " ".join(s["text"] for s in group),
            "section":    group[0]["section"],
            "subsection": group[0]["subsection"],
            "page_start": min(pages) if pages else None,
            "page_end":   max(pages) if pages else None,
        }

    chunks:  list[dict] = []
    current: list[dict] = []
    cur_len: int         = 0

    for sent in tagged:
        sent_len = len(sent["text"])

        if cur_len + sent_len + 1 > size and cur_len > 0:
            chunks.append(_finalize(current))

            # Cümle bazlı overlap: son N cümleyi tut
            current = current[-overlap_sentences:] if overlap_sentences else []
            cur_len = sum(len(s["text"]) + 1 for s in current)

        # Tek cümle size'ı aşıyorsa direkt ekle (bölme yapma)
        current.append(sent)
        cur_len += sent_len + 1

    if current:
        chunks.append(_finalize(current))

    return chunks


# ══════════════════════════════════════════════════════════════════
# ABSTRACT CHUNKING
# ══════════════════════════════════════════════════════════════════

def chunk_abstract(abstract: str, max_len: int = 500) -> list[str]:
    """
    Abstract için tek parça temsil.
    max_len aşılırsa son uygun cümle sınırında keser.
    Overlap uygulanmaz (tek chunk). Bölüm/sayfa kavramı yoktur.
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
) -> tuple[list[dict], list[dict], list[str]]:
    """
    title    → chunk yapılmaz, direkt kayıt
    abstract → chunk_abstract()
    fulltext → chunk_fulltext()  — section/subsection/page_start/page_end dahil

    Döner: (records, ft_chunks, abs_chunks)
    records: Postgres `chunks` tablosuna yazılacak tam kayıt listesi.
    ft_chunks: [{"text","section","subsection","page_start","page_end"}, ...]
               — Milvus'a embed edilirken de kullanılır (bkz. routers/database_router.py).
    """
    records: list[dict] = []

    # Başlık — tek kayıt, chunk yok, bölüm/sayfa kavramı yok
    if title:
        records.append({
            "chunk_text": title, "chunk_idx": 0, "chunk_type": "title",
            "section": "", "subsection": "", "page_start": None, "page_end": None,
        })

    # Özet
    abs_chunks = chunk_abstract(abstract)
    for i, ch in enumerate(abs_chunks):
        records.append({
            "chunk_text": ch, "chunk_idx": i, "chunk_type": "abstract",
            "section": "", "subsection": "", "page_start": None, "page_end": None,
        })

    # Tam metin
    ft_chunks = chunk_fulltext(fulltext)
    for i, ch in enumerate(ft_chunks):
        records.append({
            "chunk_text": ch["text"], "chunk_idx": i, "chunk_type": "fulltext",
            "section": ch["section"], "subsection": ch["subsection"],
            "page_start": ch["page_start"], "page_end": ch["page_end"],
        })

    return records, ft_chunks, abs_chunks
