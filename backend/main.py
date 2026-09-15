# -*- coding: utf-8 -*-
"""
main.py
════════
Başlangıçta:
  - Logging yapılandırılır
  - PostgreSQL bağlantısı test edilir
  - Milvus koleksiyonları kontrol edilir (yoksa oluşturulur)
  - Kapanışta bağlantı havuzu kapatılır
"""

import asyncio
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

# Router/servis modülleri import edilirken os.getenv() ile okunan tüm
# ayarlar (services/config.py) doğru değerleri görsün diye .env dosyası
# HERHANGİ bir proje modülü import edilmeden ÖNCE yüklenmelidir.
load_dotenv()

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.auth_router       import router as auth_router
from routers.chat_router       import router as chat_router
from routers.database_router  import router as database_router
from routers.pdf_router        import router as pdf_router
from routers.suggest_router    import router as suggest_router
from services.auth import get_current_user
from services.config import CORS_ORIGINS, OPENROUTER_API_KEY

# ── Logging ──────────────────────────────────────────────────────
# Windows konsolları varsayılan olarak UTF-8 olmayan bir codepage (örn.
# cp1254) kullanabilir; log mesajlarındaki "✓"/"═" gibi karakterler bu
# durumda UnicodeEncodeError ile sessizce (ama gürültülü şekilde) başarısız
# olur. stdout'u açıkça UTF-8'e zorluyoruz.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass  # örn. stdout yeniden yönlendirilmiş/kapalıysa (bazı servis/CI ortamları)

# Çalışma dizininden bağımsız, main.py'ye göre sabit bir konum kullanılır;
# döndürme (rotation) ile log dosyasının sınırsız büyümesi engellenir.
_LOG_DIR = Path(os.getenv("LOG_DIR", Path(__file__).resolve().parent))
_LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(
            _LOG_DIR / "altayai.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)

# ── App ──────────────────────────────────────────────────────────
app = FastAPI(
    title="AltayAI",
    description="RAG Tabanlı Akademik PDF Sohbet ve Proje Öneri Sistemi",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Router kaydı ─────────────────────────────────────────────────
# NOT: prefix'ler frontend/services/service.js'deki çağrı yollarıyla
# (/pdf/..., /chat/...) birebir eşleşmelidir.
#
# auth_router hariç TÜM router'lar geçerli bir oturum (giriş yapmış kullanıcı)
# gerektirir — database_router içindeki add/remove/reset/reconcile gibi
# yıkıcı uçlar ayrıca kendi route'unda require_admin ile admin rolü de ister.
app.include_router(auth_router, prefix="/auth")
app.include_router(database_router,   prefix="/db",      dependencies=[Depends(get_current_user)])
app.include_router(chat_router,       prefix="/chat",    dependencies=[Depends(get_current_user)])
app.include_router(pdf_router,        prefix="/pdf",     dependencies=[Depends(get_current_user)])
app.include_router(suggest_router,    prefix="/suggest", dependencies=[Depends(get_current_user)])


@app.get("/health")
async def health():
    """Load balancer / uptime kontrolü için genel sağlık ucu."""
    checks: dict[str, bool] = {}

    try:
        from services.database.postgres_service import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["postgres"] = True
    except Exception:
        checks["postgres"] = False

    try:
        from services.database.milvus_service import milvus_stats
        await asyncio.get_running_loop().run_in_executor(None, milvus_stats)
        checks["milvus"] = True
    except Exception:
        checks["milvus"] = False

    ok = all(checks.values())
    return {"status": "ok" if ok else "degraded", "checks": checks}


# ── Startup ──────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    logger.info("═" * 55)
    logger.info("AltayAI başlatılıyor…")

    # 1. PostgreSQL bağlantı testi
    try:
        from services.database.postgres_service import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        logger.info("[✓] PostgreSQL bağlantısı başarılı")
    except Exception as exc:
        logger.critical("[✗] PostgreSQL bağlanamadı: %s", exc)

    # 2. Milvus koleksiyonları kontrol — yoksa oluştur
    try:
        from services.database.init_milvus import create_all_collections
        create_all_collections()
        logger.info("[✓] Milvus koleksiyonları hazır")
    except Exception as exc:
        logger.error("[✗] Milvus başlatma hatası: %s", exc)

    # 3. OpenRouter API anahtarı kontrolü (ağ çağrısı yapılmaz — ücretsiz değil)
    if OPENROUTER_API_KEY:
        logger.info("[✓] OPENROUTER_API_KEY ayarlanmış")
    else:
        logger.warning("[!] OPENROUTER_API_KEY ayarlanmamış — LLM özellikleri çalışmayacak")

    # 4. Senkronize olmayan kayıtları raporla
    try:
        from services.database.postgres_service import pg_get_unsynced
        unsynced = await pg_get_unsynced()
        if unsynced:
            logger.warning(
                "[!] %d adet milvus_synced=FALSE kayıt var. "
                "POST /database/reconcile ile düzeltilebilir.",
                len(unsynced),
            )
        else:
            logger.info("[✓] Tüm kayıtlar Milvus ile senkronize")
    except Exception as exc:
        logger.error("[!] Senkronizasyon kontrolü başarısız: %s", exc)

    logger.info("AltayAI hazır → http://localhost:8000")
    logger.info("═" * 55)


# ── Shutdown ─────────────────────────────────────────────────────
@app.on_event("shutdown")
async def shutdown():
    from services.database.postgres_service import close_pool
    await close_pool()
    logger.info("AltayAI kapatıldı.")