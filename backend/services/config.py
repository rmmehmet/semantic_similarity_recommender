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

# ── HuggingFace Hub ──────────────────────────────────────────────
# Gömme modeli (aşağıdaki EMBEDDING_MODEL) ilk çalıştırmada indirilip
# yerel önbelleğe alınır. Varsayılan olarak offline moda
# zorlanır — aksi halde sentence-transformers her istekte HuggingFace
# Hub'a HEAD/GET istekleri atarak gereksiz gecikme ekler (LLM'e giden
# isteklerden hemen önce görülen huggingface.co logları buradan gelir).
# Modeli güncellemek/yeniden indirmek gerekirse .env'de HF_HUB_OFFLINE=0
# yapılabilir.
os.environ["HF_HUB_OFFLINE"] = os.getenv("HF_HUB_OFFLINE", "1")

# ── Embedding Modeli ─────────────────────────────────────────────
# Başlık/özet/tam-metin chunk'larının gömülmesinde kullanılan tek model —
# chat_service.py, suggest_service.py ve database_router.py hepsi buradan
# okur (eskiden üçünde de ayrı ayrı hardcode edilmişti).
#
# ÖNEMLİ: Bu değeri değiştirmek EMBEDDING_DIM'i de değiştirebilir, ki bu da
# Milvus koleksiyon şemasını (vektör boyutu) etkiler — mevcut tüm PDF'lerin
# yeniden embed edilip Milvus'a yeniden yazılması gerekir (bkz.
# scripts/reembed_all.py). Sadece model adını değiştirip uygulamayı yeniden
# başlatmak YETMEZ.
EMBEDDING_MODEL: str = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
)
EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "768"))

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

# ── API dokümantasyonu ───────────────────────────────────────────
# /docs, /redoc ve /openapi.json production'da genelde kapatılır (iç API
# şeklini herkese açık etmemek için). Portföy amaçlı sergilemek isteniyorsa
# bilinçli olarak "true" yapılabilir — varsayılan kapalı.
ENABLE_DOCS: bool = os.getenv("ENABLE_DOCS", "false").lower() == "true"

# ── Rate limiting ────────────────────────────────────────────────
RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
# Auth uçları (login/register/şifre değişimi) için ayrı ve daha sıkı bir
# limit — brute-force denemelerine karşı genel API limitinden bağımsız
# kendi sayacını tutar.
AUTH_RATE_LIMIT_PER_MINUTE: int = int(os.getenv("AUTH_RATE_LIMIT_PER_MINUTE", "10"))

# ── OpenRouter (LLM) ─────────────────────────────────────────────
# Lokal Ollama yerine OpenRouter üzerinden Llama 3.1 8B Instruct çağrılır.
# OPENROUTER_API_KEY ZORUNLUDUR — ayarlanmazsa LLM özellikleri devre dışı
# kalır (bkz. services/llm/*.py). .env dosyası .gitignore'da olduğundan
# anahtar asla repoya commit edilmez — sadece .env.example'da boş placeholder
# tutulur.
OPENROUTER_API_KEY: str | None = os.getenv("OPENROUTER_API_KEY") or None
OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")

# Reranking için kullanılan model — OpenRouter'da ayrı bir rerank API'si
# olmadığından, aynı chat-completions altyapısı üzerinden bir sıralama
# çağrısı yapılır (bkz. services/llm/reranker.py). Varsayılan olarak ana
# LLM ile aynıdır; istenirse daha ucuz/hızlı bir modelle değiştirilebilir.
RERANK_MODEL: str = os.getenv("RERANK_MODEL", OPENROUTER_MODEL)

# ── Kullanıcı Auth (JWT) ─────────────────────────────────────────
# JWT_SECRET ZORUNLUDUR — services/security.py import edilirken kontrol
# edilir ve ayarlanmamışsa uygulama başlamaz (bkz. o modüldeki hata mesajı).
# Üretmek için: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET: str | None = os.getenv("JWT_SECRET") or None
JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)))  # 7 gün

# Kayıt olurken bu listedeki e-postalarla açılan hesap otomatik "admin"
# rolü alır — herkes rolünü kendi seçemez. Virgülle ayrılmış, küçük harfe
# duyarsız (karşılaştırma sırasında lower() uygulanır).
ADMIN_EMAILS: set[str] = {
    e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()
}

# Oturum çerezi — httpOnly, JS'den erişilemez (XSS'e karşı).
AUTH_COOKIE_NAME: str = "altayai_token"
# Production'da HTTPS üzerinden servis ediliyorsa COOKIE_SECURE=true olmalı;
# yerel http://localhost geliştirmede tarayıcı Secure çerezi kabul etmez.
COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
