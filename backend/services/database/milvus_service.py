"""
milvus_service.py
-----------------
Milvus vector DB katmanı.
Koleksiyonlar: liftup_titles | liftup_abstracts | liftup_fulltext

DÜZELTMELER (v2):
  - milvus_stats(): col.flush() kaldırıldı (gereksiz I/O + num_entities'i blokluyor)
  - get_collection(): load() her çağrıda çağrılmıyor → load_state kontrolü eklendi
  - _delete_by_pdf_name: pdf_name içinde tırnak işareti olursa injection riski var
    → parametre sanitize edildi
  - milvus_insert_*: field adlarına göre dict-based insert kullanıldı (pozisyon hatası önlenir)
  - ensure_connected: basit lock benzeri flag, uvicorn single-thread için yeterli
"""

from __future__ import annotations

import os
import re
from typing import Optional

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

# ── Bağlantı ──────────────────────────────────────────────────────
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_DB   = os.getenv("MILVUS_DB",   "liftup_db")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))

COL_TITLES    = "liftup_titles"
COL_ABSTRACTS = "liftup_abstracts"
COL_FULLTEXT  = "liftup_fulltext"

DIM = 384  # paraphrase-multilingual-MiniLM-L12-v2

_connected = False


def ensure_connected() -> None:
    global _connected
    if not _connected:
        connections.connect(
            "default",
            host=MILVUS_HOST,
            port=MILVUS_PORT,
            db_name=MILVUS_DB,
        )
        _connected = True


def _safe_name(pdf_name: str) -> str:
    """PDF adındaki tırnak / özel karakterleri temizler (Milvus expr injection önlemi)."""
    return pdf_name.replace('"', "").replace("'", "").replace("\\", "")


def get_collection(name: str) -> Collection:
    ensure_connected()
    col = Collection(name)
    # Zaten yüklüyse tekrar load() çağırmak gereksiz yük oluşturur
    load_state = utility.load_state(name)
    if str(load_state) != "Loaded":
        col.load()
    return col


# ══════════════════════════════════════════════════════════════════
# INSERT
# Pymilvus dict-based insert kullanılıyor → field sırası hatası yok
# ══════════════════════════════════════════════════════════════════

def milvus_insert_title(pdf_name: str, title: str, vector: list[float]) -> int:
    """liftup_titles'a 1 kayıt ekler. Döndürür: Milvus primary key."""
    col = get_collection(COL_TITLES)
    data = [
        {"pdf_name": pdf_name, "text": title, "vector": vector}
    ]
    res = col.insert(data)
    col.flush()
    return int(res.primary_keys[0])


def milvus_insert_abstract(pdf_name: str, abstract: str, vector: list[float]) -> int:
    """liftup_abstracts'a 1 kayıt ekler."""
    col = get_collection(COL_ABSTRACTS)
    data = [
        {"pdf_name": pdf_name, "text": abstract, "vector": vector}
    ]
    res = col.insert(data)
    col.flush()
    return int(res.primary_keys[0])


def milvus_insert_fulltext_chunks(
    pdf_name: str,
    chunks: list[str],
    vectors: list[list[float]],
) -> list[int]:
    """
    liftup_fulltext'e N chunk ekler.
    chunks[i] ↔ vectors[i]
    """
    if not chunks:
        return []
    col = get_collection(COL_FULLTEXT)
    data = [
        {
            "pdf_name":  pdf_name,
            "chunk_idx": i,
            "text":      chunk,
            "vector":    vectors[i],
        }
        for i, chunk in enumerate(chunks)
    ]
    res = col.insert(data)
    col.flush()
    return [int(pk) for pk in res.primary_keys]


# ══════════════════════════════════════════════════════════════════
# DELETE
# ══════════════════════════════════════════════════════════════════

def _delete_by_pdf_name(collection_name: str, pdf_name: str) -> None:
    safe = _safe_name(pdf_name)
    col  = get_collection(collection_name)
    col.delete(expr=f'pdf_name == "{safe}"')
    col.flush()


def milvus_delete_pdf(pdf_name: str) -> None:
    """3 koleksiyondan da siler."""
    for name in [COL_TITLES, COL_ABSTRACTS, COL_FULLTEXT]:
        try:
            _delete_by_pdf_name(name, pdf_name)
        except Exception:
            pass  # koleksiyon yoksa veya boşsa sessizce geç


# ══════════════════════════════════════════════════════════════════
# SEARCH
# ══════════════════════════════════════════════════════════════════

def milvus_search(
    collection_name: str,
    query_vector: list[float],
    top_k: int = 10,
    output_fields: Optional[list[str]] = None,
    expr: Optional[str] = None,
) -> list[dict]:
    """
    En yakın top_k kaydı döndürür.
    output_fields belirtilmezse ['pdf_name', 'text'] döner.
    expr: opsiyonel scalar filtre, örn. 'pdf_name != "xyz.pdf"'
    """
    col = get_collection(collection_name)
    if output_fields is None:
        output_fields = ["pdf_name", "text"]

    search_params = {
        "metric_type": "COSINE",
        "params": {"ef": 128},
    }

    results = col.search(
        data=[query_vector],
        anns_field="vector",
        param=search_params,
        limit=top_k,
        expr=expr,
        output_fields=output_fields,
    )

    hits = []
    for hit in results[0]:
        record: dict = {"score": round(float(hit.score), 6), "id": hit.id}
        for field in output_fields:
            record[field] = hit.entity.get(field)
        hits.append(record)
    return hits


# ══════════════════════════════════════════════════════════════════
# QUERY (exact match — mevcutluk kontrolü)
# ══════════════════════════════════════════════════════════════════

def milvus_pdf_exists(pdf_name: str) -> bool:
    """liftup_titles'da bu pdf_name var mı?"""
    try:
        col = get_collection(COL_TITLES)
        safe = _safe_name(pdf_name)
        res = col.query(
            expr=f'pdf_name == "{safe}"',
            output_fields=["pdf_name"],
            limit=1,
        )
        return len(res) > 0
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════
# İSTATİSTİKLER
# flush() KALDIRILDI — num_entities anlık sayıyı döndürür
# ══════════════════════════════════════════════════════════════════

def milvus_stats() -> dict:
    ensure_connected()
    stats: dict = {}
    for name in [COL_TITLES, COL_ABSTRACTS, COL_FULLTEXT]:
        if utility.has_collection(name):
            col = Collection(name)
            stats[name] = {"count": col.num_entities}
        else:
            stats[name] = {"count": 0, "error": "collection not found"}
    return stats


# ══════════════════════════════════════════════════════════════════
# RESET — koleksiyonları drop + yeniden oluştur
# ══════════════════════════════════════════════════════════════════

def milvus_drop_all() -> None:
    ensure_connected()
    for name in [COL_TITLES, COL_ABSTRACTS, COL_FULLTEXT]:
        if utility.has_collection(name):
            Collection(name).drop()