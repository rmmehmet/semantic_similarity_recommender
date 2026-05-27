from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import pdf_router
from routers.similarity_router import router as similarity_router
from routers.database_router   import router as db_router
from routers.suggest_router import router as suggest_router

from services.database.postgres_service import get_pool, close_pool
from services.database.init_milvus      import create_all_collections

# ══════════════════════════════════════════════════════════════════
# APPLICATION LIFESPAN (startup / shutdown)
# ══════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────
    print("▶ Creating PostgreSQL connection pool…")
    await get_pool()

    print("▶ Creating Milvus collections…")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, create_all_collections)

    print("▶ Pre-loading embedding model…")
    from routers.database_router import _get_model
    await loop.run_in_executor(None, _get_model)

    print("✓ All systems go! API is ready to accept requests.")
    yield

    # ── Shutdown ─────────────────────────────────────────────────
    print("◀ PostgreSQL connection pool is closing…")
    await close_pool()

# ══════════════════════════════════════════════════════════════════
# APPLICATION SETUP
# ══════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Altay AI Backend API",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ══════════════════════════════════════════════════════════════════
# ROUTERS  —  PDF, SIMILARITY, DATABASE
# ══════════════════════════════════════════════════════════════════

app.include_router(pdf_router.router,   prefix="/pdf",        tags=["PDF"])
app.include_router(similarity_router,   prefix="/similarity",  tags=["Similarity"])
app.include_router(db_router,           prefix="/db",          tags=["Database"])
app.include_router(suggest_router,      prefix="/suggest",     tags=["Suggest"])

# ══════════════════════════════════════════════════════════════════
# GENERAL ENDPOINT'LER
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