# -*- coding: utf-8 -*-
"""
services/config.py
════════════════════
Ortam değişkenlerinden okunan, production/dev arasında değişen tüm ayarlar
tek bir yerde toplanır. Hiçbir modül burada olmayan bir default'u
kaynak koduna hardcode etmemelidir.
"""

from __future__ import annotations

import os

# ── CORS ─────────────────────────────────────────────────────────
# Virgülle ayrılmış origin listesi, örn:
#   CORS_ORIGINS=https://altayai.example.com,https://www.altayai.example.com
# Ayarlanmazsa sadece yerel geliştirme origin'lerine izin verilir.
_default_dev_origins = "http://localhost:5173,http://127.0.0.1:5173"
CORS_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", _default_dev_origins).split(",")
    if origin.strip()
]

# ── Admin API Key ────────────────────────────────────────────────
# Yıkıcı/idari uçlar (reset, remove, reconcile, add) bu anahtarı
# `X-API-Key` header'ında bekler. Ayarlanmazsa (dev ortamı) auth atlanır
# ama bir uyarı loglanır — bkz. services/auth.py.
ADMIN_API_KEY: str | None = os.getenv("ADMIN_API_KEY") or None

# ── Upload limitleri ─────────────────────────────────────────────
MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "30"))
MAX_UPLOAD_BYTES: int = MAX_UPLOAD_MB * 1024 * 1024

# ── Rate limiting ────────────────────────────────────────────────
RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))

# ── Ollama ───────────────────────────────────────────────────────
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
