from __future__ import annotations

import os

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
MILVUS_DB   = os.getenv("MILVUS_DB",   "liftup_db")
DIM         = 384  # paraphrase-multilingual-MiniLM-L12-v2 çıktı boyutu

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
            FieldSchema("pdf_name",  DataType.VARCHAR,      max_length=512),
            FieldSchema("chunk_idx", DataType.INT32),
            FieldSchema("text",      DataType.VARCHAR,      max_length=2048),
            FieldSchema("vector",    DataType.FLOAT_VECTOR, dim=DIM),
        ],
        desc="PDF fulltext collection — for RAG retrieval (chunk-based)",
    )

    print("✓ All collections are ready.")


def _ensure_collection(
    name: str,
    fields: list[FieldSchema],
    desc: str,
) -> Collection:
    if utility.has_collection(name):
        print(f"  – {name}: already exists, loading.")
        col = Collection(name)
        col.load()
        return col

    schema = CollectionSchema(fields=fields, description=desc)
    col    = Collection(name=name, schema=schema)
    col.create_index(field_name="vector", index_params=HNSW_INDEX)
    col.load()
    print(f"  ✓ {name}: created.")
    return col


if __name__ == "__main__":
    create_all_collections()