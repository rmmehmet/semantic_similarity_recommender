from __future__ import annotations

import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

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
    """Removes quotation marks/special characters from the PDF file (Milvus expr injection precaution)."""
    return pdf_name.replace('"', "").replace("'", "").replace("\\", "")


def get_collection(name: str) -> Collection:
    """Get a Milvus collection by name, ensuring it's loaded. Raises an error if the collection doesn't exist.
    Parameters:
    name (str): The name of the collection to retrieve.
    Returns:
    Collection: The Milvus collection object."""
    ensure_connected()
    col = Collection(name)
    # Calling load() again if it's already loaded creates unnecessary overhead
    load_state = utility.load_state(name)
    if str(load_state) != "Loaded":
        col.load()
    return col

# ══════════════════════════════════════════════════════════════════
# INSERT
# ══════════════════════════════════════════════════════════════════

def milvus_insert_title(pdf_name: str, title: str, vector: list[float]) -> int:
    """Adds 1 entry to liftup_titles.
    Parameters:
    pdf_name (str): The name of the PDF file.
    title (str): The title of the paper.
    vector (list[float]): The embedding vector for the title.
    Returns:
    int: The primary key of the inserted entry."""
    col = get_collection(COL_TITLES)
    data = [
        {"pdf_name": pdf_name, "text": title, "vector": vector}
    ]
    res = col.insert(data)
    col.flush()
    return int(res.primary_keys[0])

def milvus_insert_abstract(pdf_name: str, abstract: str, vector: list[float]) -> int:
    """Adds 1 entry to liftup_abstracts.
    Parameters:
    pdf_name (str): The name of the PDF file.
    abstract (str): The abstract of the paper.
    vector (list[float]): The embedding vector for the abstract.
    Returns:
    int: The primary key of the inserted entry."""
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
    """Adds N entries to liftup_fulltext for the given PDF.
    Parameters:
    pdf_name (str): The name of the PDF file.
    chunks (list[str]): The list of full text chunks.
    vectors (list[list[float]]): The list of embedding vectors corresponding to each chunk.
    Returns:
    list[int]: The list of primary keys of the inserted entries.
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
    """Deletes all entries with the given pdf_name from the specified collection.
    Parameters:
    collection_name (str): The name of the collection from which to delete entries.
    pdf_name (str): The name of the PDF file whose entries to delete.
    Returns:
    None: This function does not return anything."""
    safe = _safe_name(pdf_name)
    col  = get_collection(collection_name)
    col.delete(expr=f'pdf_name == "{safe}"')
    col.flush()

def milvus_delete_pdf(pdf_name: str) -> None:
    """3 koleksiyondan da siler."""
    for name in [COL_TITLES, COL_ABSTRACTS, COL_FULLTEXT]:
        try:
            _delete_by_pdf_name(name, pdf_name)
        except Exception as exc:
            # Koleksiyon yoksa/başka bir hata varsa devam et ama sessizce yutma.
            logger.warning("[Milvus] %s koleksiyonundan silinemedi (%s): %s", name, pdf_name, exc)

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
    """Performs a similarity search on the specified collection using the given query vector and optional filter expression.
    Parameters:
    collection_name (str): The name of the collection to search.
    query_vector (list[float]): The embedding vector to use as the search query.
    top_k (int, optional): The number of top results to return. Defaults to 10.
    output_fields (list[str], optional): The list of additional fields to include in the results. Defaults to None (only returns id and score).
    expr (str, optional): An optional filter expression to apply to the search. Defaults to None (no filtering).
    Returns:
    list[dict]: A list of search results, where each result is a dictionary containing the score, id, and any requested output fields.
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
# QUERY (exact match)
# ══════════════════════════════════════════════════════════════════

def milvus_pdf_exists(pdf_name: str) -> bool:
    """Checks if an entry with the given pdf_name exists in the liftup_titles collection. This is used as a proxy to check if the PDF has been processed, since each PDF should have exactly 1 title entry.
    Parameters:
    pdf_name (str): The name of the PDF file to check.
    Returns:
    bool: True if an entry with the given pdf_name exists, False otherwise."""
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
# STATS
# ══════════════════════════════════════════════════════════════════

def milvus_stats() -> dict:
    """Returns the number of entries in each collection. This can be used to monitor how many PDFs have been processed and stored in Milvus.
    Returns:
        dict: A dictionary containing the count of entries in each collection.
    """
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
# RESET
# ══════════════════════════════════════════════════════════════════

def milvus_drop_all() -> None:
    """Drops all collections. Use with caution, this will delete all data in Milvus.
    Returns:
        None
    """
    ensure_connected()
    for name in [COL_TITLES, COL_ABSTRACTS, COL_FULLTEXT]:
        if utility.has_collection(name):
            Collection(name).drop()

# ══════════════════════════════════════════════════════════════════
# RECONCILE YARDIMCISI
# ══════════════════════════════════════════════════════════════════

_QUERY_PAGE_SIZE = 4096


def milvus_get_all_pdf_names() -> set[str]:
    """
    3 koleksiyondaki tüm benzersiz pdf_name'leri döner.
    Reconcile karşılaştırması için kullanılır. Koleksiyon boyutu
    sayfa boyutunu aşabileceğinden offset/limit ile sayfalanır.
    """
    ensure_connected()
    all_names: set[str] = set()

    for col_name in [COL_TITLES, COL_ABSTRACTS, COL_FULLTEXT]:
        if not utility.has_collection(col_name):
            continue
        try:
            col = get_collection(col_name)
            offset = 0
            while True:
                res = col.query(
                    expr="pdf_name != \"\"",
                    output_fields=["pdf_name"],
                    limit=_QUERY_PAGE_SIZE,
                    offset=offset,
                )
                for r in res:
                    name = r.get("pdf_name", "").strip()
                    if name:
                        all_names.add(name)
                if len(res) < _QUERY_PAGE_SIZE:
                    break
                offset += _QUERY_PAGE_SIZE
        except Exception as exc:
            logger.warning("[Milvus] %s sorgulanamadı: %s", col_name, exc)

    return all_names