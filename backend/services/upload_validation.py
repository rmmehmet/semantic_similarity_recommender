# -*- coding: utf-8 -*-
"""
services/upload_validation.py
════════════════════════════════
Yüklenen dosyalar için ortak boyut/tip kontrolü. Bellek tükenmesini
(çok büyük dosya) ve PDF olmayan dosyaların işlem hattına girmesini önler.
"""

from __future__ import annotations

from fastapi import HTTPException, UploadFile

from services.config import MAX_UPLOAD_BYTES, MAX_UPLOAD_MB

PDF_MAGIC = b"%PDF-"


def validate_pdf_bytes(data: bytes, filename: str | None = None) -> None:
    if not data:
        raise HTTPException(status_code=400, detail="Dosya boş.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya çok büyük. Maksimum {MAX_UPLOAD_MB} MB desteklenir.",
        )
    if data[:5] != PDF_MAGIC:
        raise HTTPException(status_code=400, detail="Geçersiz dosya — PDF bekleniyor.")


async def read_and_validate_pdf(file: UploadFile) -> bytes:
    data = await file.read()
    validate_pdf_bytes(data, file.filename)
    return data
