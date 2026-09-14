# -*- coding: utf-8 -*-
"""
services/auth.py
══════════════════
Yıkıcı/idari endpoint'ler (reset, remove, reconcile, add) için basit
API-key doğrulaması. `X-API-Key` header'ı `ADMIN_API_KEY` ortam
değişkenine eşit olmalıdır.

ADMIN_API_KEY ayarlanmamışsa (yerel geliştirme), doğrulama atlanır ve
her başlatmada uyarı loglanır — production'da bu değişken MUTLAKA
ayarlanmalıdır.
"""

from __future__ import annotations

import logging
import secrets

from fastapi import Header, HTTPException

from services.config import ADMIN_API_KEY

logger = logging.getLogger(__name__)

if not ADMIN_API_KEY:
    logger.warning(
        "[Auth] ADMIN_API_KEY tanımlı değil — idari uçlar (reset/remove/reconcile) "
        "kimlik doğrulaması OLMADAN açık. Production'da bu değişkeni ayarlayın."
    )


async def require_admin_key(x_api_key: str | None = Header(default=None)) -> None:
    if not ADMIN_API_KEY:
        # Dev ortamı — auth atlanır (yukarıda uyarı loglandı).
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik API anahtarı")
