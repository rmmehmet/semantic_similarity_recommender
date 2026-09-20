# -*- coding: utf-8 -*-
"""
services/security.py
══════════════════════
Şifre hash'leme (bcrypt) ve JWT oturum token'ı üretim/doğrulama.

Güvenlik notları:
  - Şifreler asla düz metin olarak saklanmaz — bcrypt (salt dahili) kullanılır.
  - JWT_SECRET ayarlanmamışsa uygulama BAŞLAMAZ (aşağıda import-time kontrol).
    Sahte/varsayılan bir secret ile "çalışıyor gibi görünüp" imzası tahmin
    edilebilir token üretmektense, açıkça hata verip durmak tercih edilir.
  - bcrypt 72 byte'tan uzun şifreleri sessizce keser; bu yüzden kayıt
    şemasında (routers/auth_router.py) şifre uzunluğu ayrıca sınırlanır.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import bcrypt
import jwt
from fastapi import HTTPException

from services.config import JWT_EXPIRE_MINUTES, JWT_SECRET

if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET ortam değişkeni tanımlı değil. Kullanıcı oturumları "
        "güvenli bir imza anahtarı olmadan asla açılmamalı. "
        "Üretmek için: python -c \"import secrets; print(secrets.token_hex(32))\" "
        "ve backend/.env dosyasına JWT_SECRET=... olarak ekleyin."
    )

_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user: dict[str, Any]) -> str:
    """user: en az id, email, role, first_name, last_name, token_version alanlarını içermeli."""
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub":            str(user["id"]),
        "email":          user["email"],
        "role":           user["role"],
        "first_name":     user["first_name"],
        "last_name":      user["last_name"],
        "token_version":  user["token_version"],
        "iat":            now,
        "exp":            now + dt.timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Oturum süresi doldu, tekrar giriş yapın.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Geçersiz oturum.")
