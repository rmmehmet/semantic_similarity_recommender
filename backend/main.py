"""
main.py
-------
FastAPI uygulama giriş noktası.

Startup:
  - PostgreSQL bağlantı havuzu oluşturulur
  - Milvus koleksiyonları kontrol edilir / oluşturulur
  - Embedding modeli ön yüklenir

Shutdown:
  - PostgreSQL havuzu kapatılır
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import pdf_router
from routers.similarity_router import router as similarity_router
from routers.database_router   import router as db_router

from services.database.postgres_service import get_pool, close_pool
from services.database.init_milvus      import create_all_collections


# ══════════════════════════════════════════════════════════════════
# UYGULAMA YAŞAM DÖNGÜSÜ  (startup / shutdown)
# ══════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────
    print("▶ PostgreSQL bağlantı havuzu başlatılıyor…")
    await get_pool()

    print("▶ Milvus koleksiyonları kontrol ediliyor…")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, create_all_collections)

    print("▶ Embedding modeli ön yükleniyor…")
    from routers.database_router import _get_model
    await loop.run_in_executor(None, _get_model)

    print("✓ Tüm servisler hazır.")
    yield

    # ── Shutdown ─────────────────────────────────────────────────
    print("◀ PostgreSQL bağlantı havuzu kapatılıyor…")
    await close_pool()


# ══════════════════════════════════════════════════════════════════
# UYGULAMA
# ══════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Altay AI Backend API",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # mevcut ayarın korundu
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ══════════════════════════════════════════════════════════════════
# ROUTER'LAR  —  prefix'ler mevcut main.py ile aynı tutuldu
# ══════════════════════════════════════════════════════════════════

app.include_router(pdf_router.router,   prefix="/pdf",        tags=["PDF"])
app.include_router(similarity_router,   prefix="/similarity",  tags=["Similarity"])
app.include_router(db_router,           prefix="/db",          tags=["Database"])


# ══════════════════════════════════════════════════════════════════
# GENEL ENDPOINT'LER
# ══════════════════════════════════════════════════════════════════

@app.get("/")
async def read_root():
    return {"message": "Altay AI Backend API is running!"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ══════════════════════════════════════════════════════════════════
# GELİŞTİRME SUNUCUSU
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)