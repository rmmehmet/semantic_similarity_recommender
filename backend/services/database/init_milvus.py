from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
    db
)

# Önce bağlantı
connections.connect(
    alias="default",
    host="localhost",
    port="19530"
)

# Database adı
DB_NAME = "liftup_db"

# Database yoksa oluştur
existing_dbs = db.list_database()

if DB_NAME not in existing_dbs:
    db.create_database(DB_NAME)

# Aktif database seç
db.using_database(DB_NAME)

DIM = 384  # paraphrase-multilingual-MiniLM-L12-v2 boyutu

def create_collection(name, has_chunk_idx=False):

    if utility.has_collection(name):
        return Collection(name)

    fields = [
        FieldSchema(
            name="id",
            dtype=DataType.INT64,
            is_primary=True,
            auto_id=True
        ),

        FieldSchema(
            name="pdf_name",
            dtype=DataType.VARCHAR,
            max_length=256
        ),

        FieldSchema(
            name="text",
            dtype=DataType.VARCHAR,
            max_length=4096
        ),

        FieldSchema(
            name="vector",
            dtype=DataType.FLOAT_VECTOR,
            dim=DIM
        ),
    ]

    if has_chunk_idx:
        fields.insert(
            3,
            FieldSchema(
                name="chunk_idx",
                dtype=DataType.INT32
            )
        )

    schema = CollectionSchema(
        fields=fields,
        description=name
    )

    col = Collection(
        name=name,
        schema=schema
    )

    # HNSW index
    col.create_index(
        field_name="vector",
        index_params={
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {
                "M": 16,
                "efConstruction": 200
            }
        }
    )

    col.load()

    return col


# Koleksiyonlar
create_collection("liftup_titles")
create_collection("liftup_abstracts")
create_collection("liftup_fulltext", has_chunk_idx=True)

print(f"{DB_NAME} database'i içinde koleksiyonlar hazır.")