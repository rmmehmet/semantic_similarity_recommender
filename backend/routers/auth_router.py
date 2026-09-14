# -*- coding: utf-8 -*-
"""
routers/auth_router.py
════════════════════════
Kayıt / giriş / çıkış / mevcut kullanıcı uçları.

  POST /auth/register  → e-posta, ad, soyad, telefon, şifre(x2) ile hesap açar
  POST /auth/login     → e-posta + şifre ile giriş yapar
  POST /auth/logout    → oturum çerezini siler
  GET  /auth/me        → mevcut oturumun bilgisini döner

Oturum httpOnly bir çerezde taşınan JWT ile tutulur (bkz. services/security.py,
services/auth.py). Gerçek bir e-posta/SMS doğrulama adımı YOKTUR — sadece
format doğrulaması (email-validator, phonenumbers) ve "bu e-posta/telefon
zaten kayıtlı mı" kontrolü yapılır.
"""

from __future__ import annotations

import asyncio
import logging
from functools import partial

import phonenumbers
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, field_validator, model_validator

from services.auth import AUTH_COOKIE_NAME, get_current_user
from services.config import ADMIN_EMAILS, COOKIE_SECURE, JWT_EXPIRE_MINUTES
from services.database.postgres_service import (
    pg_create_user,
    pg_get_user_by_email,
    pg_get_user_by_phone,
)
from services.security import create_access_token, hash_password, verify_password

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Auth"])


# ══════════════════════════════════════════════════════════════════
# ŞEMALAR
# ══════════════════════════════════════════════════════════════════

class RegisterRequest(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    phone: str
    password: str
    password_confirm: str

    @field_validator("first_name", "last_name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("En az 2 karakter olmalı")
        if len(v) > 100:
            raise ValueError("En fazla 100 karakter olabilir")
        return v

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Şifre en az 8 karakter olmalı")
        # bcrypt 72 byte'tan uzun şifreleri sessizce keser — üst sınır koyuyoruz.
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Şifre en fazla 72 karakter olabilir")
        if not any(c.isdigit() for c in v):
            raise ValueError("Şifre en az 1 rakam içermeli")
        if not any(c.isalpha() for c in v):
            raise ValueError("Şifre en az 1 harf içermeli")
        return v

    @field_validator("phone")
    @classmethod
    def _phone_format(cls, v: str) -> str:
        v = v.strip()
        try:
            # Ülke kodu verilmemişse (+90 vb.) varsayılan olarak TR kabul edilir.
            parsed = phonenumbers.parse(v, "TR")
        except phonenumbers.NumberParseException:
            raise ValueError("Geçersiz telefon numarası formatı")
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Geçersiz telefon numarası")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

    @model_validator(mode="after")
    def _passwords_match(self) -> "RegisterRequest":
        if self.password != self.password_confirm:
            raise ValueError("Şifreler eşleşmiyor")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ══════════════════════════════════════════════════════════════════
# YARDIMCILAR
# ══════════════════════════════════════════════════════════════════

async def _hash_password_async(password: str) -> str:
    # bcrypt CPU-bound'dur (~100-300ms) — event loop'u bloklamasın.
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(hash_password, password))


async def _verify_password_async(password: str, password_hash: str) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(verify_password, password, password_hash))


def _public_user(user: dict) -> dict:
    """Şifre hash'i asla client'a dönmez."""
    return {
        "id":         user["id"],
        "email":      user["email"],
        "phone":      user["phone"],
        "first_name": user["first_name"],
        "last_name":  user["last_name"],
        "role":       user["role"],
    }


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=JWT_EXPIRE_MINUTES * 60,
        path="/",
    )


# ══════════════════════════════════════════════════════════════════
# REGISTER
# ══════════════════════════════════════════════════════════════════

@router.post("/register")
async def register(body: RegisterRequest, response: Response):
    email = body.email.lower().strip()

    if await pg_get_user_by_email(email):
        raise HTTPException(status_code=409, detail="Bu e-posta adresi zaten kayıtlı.")
    if await pg_get_user_by_phone(body.phone):
        raise HTTPException(status_code=409, detail="Bu telefon numarası zaten kayıtlı.")

    password_hash = await _hash_password_async(body.password)
    role = "admin" if email in ADMIN_EMAILS else "user"

    user = await pg_create_user(
        email=email,
        phone=body.phone,
        first_name=body.first_name,
        last_name=body.last_name,
        password_hash=password_hash,
        role=role,
    )

    token = create_access_token(user)
    _set_auth_cookie(response, token)
    logger.info("[Auth] Yeni kayıt: %s (role=%s)", email, role)

    return {"user": _public_user(user)}


# ══════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════

@router.post("/login")
async def login(body: LoginRequest, response: Response):
    email = body.email.lower().strip()
    user = await pg_get_user_by_email(email)

    # Kullanıcı yok / şifre yanlış — aynı genel mesaj (enumeration'ı önler).
    if not user or not await _verify_password_async(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı.")

    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Hesabınız devre dışı bırakılmış.")

    token = create_access_token(user)
    _set_auth_cookie(response, token)

    return {"user": _public_user(user)}


# ══════════════════════════════════════════════════════════════════
# LOGOUT
# ══════════════════════════════════════════════════════════════════

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return {"status": "ok"}


# ══════════════════════════════════════════════════════════════════
# ME
# ══════════════════════════════════════════════════════════════════

@router.get("/me")
async def me(current: dict = Depends(get_current_user)):
    return {
        "user": {
            "id":         current.get("sub"),
            "email":      current.get("email"),
            "first_name": current.get("first_name"),
            "last_name":  current.get("last_name"),
            "role":       current.get("role"),
        }
    }
