# -*- coding: utf-8 -*-
"""
services/auth.py
══════════════════
Kimlik doğrulama bağımlılıkları (FastAPI Depends).

İki mekanizma bir arada çalışır:

  1) Kullanıcı oturumu (birincil, production yolu) — httpOnly çerezde
     taşınan JWT. `get_current_user` / `get_current_user_optional` /
     `require_admin` bunu kullanır. Kayıt/giriş routers/auth_router.py'de.

  2) Statik API anahtarı (ikincil, tarayıcı dışı/otomasyon için) —
     `X-API-Key` header'ı `ADMIN_API_KEY` ortam değişkenine eşitse
     `require_admin` bunu da admin yetkisi olarak kabul eder. Hiçbiri
     ayarlanmamışsa (ne ADMIN_API_KEY ne de geçerli bir oturum) istek
     reddedilir — artık "auth tamamen kapalı" diye bir dev-modu yoktur,
     çünkü artık gerçek kullanıcı girişi var.
"""

from __future__ import annotations

import logging
import secrets

from fastapi import Header, HTTPException, Request

from services.config import ADMIN_API_KEY
from services.database.postgres_service import pg_get_user_token_version
from services.security import decode_token

logger = logging.getLogger(__name__)

AUTH_COOKIE_NAME = "altayai_token"


def _read_token(request: Request) -> str | None:
    return request.cookies.get(AUTH_COOKIE_NAME)


async def _decode_and_check_version(token: str) -> dict:
    """JWT'yi çözer VE token'daki token_version'ı DB'deki güncel değerle
    karşılaştırır. Şifre değişince DB'deki sayaç artar (bkz.
    pg_bump_token_version) — o andan önce üretilmiş tüm token'lar (JWT'nin
    kendi 7 günlük süresi henüz dolmamış olsa bile) burada elenir."""
    payload = decode_token(token)
    current_version = await pg_get_user_token_version(int(payload["sub"]))
    if current_version is None or payload.get("token_version") != current_version:
        raise HTTPException(status_code=401, detail="Oturum geçersiz, tekrar giriş yapın.")
    return payload


async def get_current_user(request: Request) -> dict:
    """Oturum ZORUNLU — token yoksa/geçersizse 401 döner."""
    token = _read_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Oturum açmanız gerekiyor.")
    return await _decode_and_check_version(token)


async def get_current_user_optional(request: Request) -> dict | None:
    """Oturum opsiyonel — token yoksa/geçersizse None döner, hata fırlatmaz."""
    token = _read_token(request)
    if not token:
        return None
    try:
        return await _decode_and_check_version(token)
    except HTTPException:
        return None


async def require_admin(
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> dict:
    """
    Yıkıcı/idari uçlar için: ya geçerli bir ADMIN_API_KEY header'ı,
    ya da rolü 'admin' olan geçerli bir kullanıcı oturumu gerekir.
    """
    if ADMIN_API_KEY and x_api_key and secrets.compare_digest(x_api_key, ADMIN_API_KEY):
        return {"sub": None, "email": "service-account", "role": "admin"}

    user = await get_current_user_optional(request)
    if user and user.get("role") == "admin":
        return user

    raise HTTPException(status_code=403, detail="Bu işlem için admin yetkisi gerekir.")
