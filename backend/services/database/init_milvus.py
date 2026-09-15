from __future__ import annotations

import logging
import os

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from services.config import EMBEDDING_DIM

logger = logging.getLogger(__name__)

MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
MILVUS_DB   = os.getenv("MILVUS_DB",   "liftup_db")
DIM         = EMBEDDING_DIM  # bkz. services/config.py — embedding modeliyle birlikte değişir

HNSW_INDEX = {
    "index_type":  "HNSW",
    "metric_type": "COSINE",
    "params": {"M": 16, "efConstruction": 200},
}


def create_all_collections() -> None:
    """Create Milvus collections if they don't exist, otherwise just load them."""
    connections.connect(
        "default",
        host=MILVUS_HOST,
        port=MILVUS_PORT,
        db_name=MILVUS_DB,
    )

    # ── liftup_titles ─────────────────────────────────────────────
    # 1 PDF → 1 entry  |  title vector
    _ensure_collection(
        name="liftup_titles",
        fields=[
            FieldSchema("id",       DataType.INT64,       is_primary=True, auto_id=True),
            FieldSchema("user_id",  DataType.INT64),
            FieldSchema("pdf_name", DataType.VARCHAR,      max_length=512),
            FieldSchema("text",     DataType.VARCHAR,      max_length=1024),
            FieldSchema("vector",   DataType.FLOAT_VECTOR, dim=DIM),
        ],
        desc="PDF title collection — for similarity title scoring",
    )

    # ── liftup_abstracts ──────────────────────────────────────────
    # 1 PDF → 1 entry  |  abstract vector
    _ensure_collection(
        name="liftup_abstracts",
        fields=[
            FieldSchema("id",       DataType.INT64,       is_primary=True, auto_id=True),
            FieldSchema("user_id",  DataType.INT64),
            FieldSchema("pdf_name", DataType.VARCHAR,      max_length=512),
            FieldSchema("text",     DataType.VARCHAR,      max_length=4096),
            FieldSchema("vector",   DataType.FLOAT_VECTOR, dim=DIM),
        ],
        desc="PDF abstract collection — for semantic search",
    )

    # ── liftup_fulltext ───────────────────────────────────────────
    # 1 PDF → N chunk  |  ful text chunk vector (RAG retrieval)
    _ensure_collection(
        name="liftup_fulltext",
        fields=[
            FieldSchema("id",        DataType.INT64,       is_primary=True, auto_id=True),
            FieldSchema("user_id",   DataType.INT64),
            FieldSchema("pdf_name",  DataType.VARCHAR,      max_length=512),
            FieldSchema("chunk_idx", DataType.INT32),
            FieldSchema("text",      DataType.VARCHAR,      max_length=2048),
            FieldSchema("vector",    DataType.FLOAT_VECTOR, dim=DIM),
        ],
        desc="PDF fulltext collection — for RAG retrieval (chunk-based)",
    )

    logger.info("Tüm koleksiyonlar hazır.")


def _ensure_collection(
    name: str,
    fields: list[FieldSchema],
    desc: str,
) -> Collection:
    expected_field_names = {f.name for f in fields}
    expected_dim = next(
        (f.params.get("dim") for f in fields if f.dtype == DataType.FLOAT_VECTOR), None
    )

    if utility.has_collection(name):
        existing = Collection(name)
        existing_field_names = {f.name for f in existing.schema.fields}
        existing_dim = next(
            (f.params.get("dim") for f in existing.schema.fields if f.dtype == DataType.FLOAT_VECTOR),
            None,
        )
        if existing_field_names == expected_field_names and existing_dim == expected_dim:
            logger.info("%s: zaten var, yükleniyor.", name)
            existing.load()
            return existing

        # Şema değişmiş (yeni alan eklendi VEYA embedding modeli değişip vektör
        # boyutu farklılaştı — bkz. services/config.py EMBEDDING_DIM). Önceki
        # veri yeni şemayla uyumsuz (özellikle dim değişiminde: aynı "vector"
        # alan adı ama farklı boyut, insert'te sessizce hata verir). Koleksiyon
        # düşürülüp yeni şemayla yeniden oluşturulur — dim değişimi durumunda
        # çağıran taraf (scripts/reembed_all.py) verileri yeniden embed edip
        # geri yazmalıdır, aksi halde koleksiyon boş kalır.
        logger.warning(
            "%s: şema değişmiş (eski alanlar=%s dim=%s, yeni alanlar=%s dim=%s) — "
            "koleksiyon düşürülüp yeniden oluşturuluyor.",
            name, sorted(existing_field_names), existing_dim,
            sorted(expected_field_names), expected_dim,
        )
        existing.drop()

    schema = CollectionSchema(fields=fields, description=desc)
    col    = Collection(name=name, schema=schema)
    col.create_index(field_name="vector", index_params=HNSW_INDEX)
    col.load()
    logger.info("%s: oluşturuldu.", name)
    return col


if __name__ == "__main__":
    create_all_collections()