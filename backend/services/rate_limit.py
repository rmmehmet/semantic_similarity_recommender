# -*- coding: utf-8 -*-
"""
services/rate_limit.py
════════════════════════
Pahalı endpoint'ler (LLM/embedding/PDF işleme) ve auth uçları (brute-force
koruması) için basit, bellek-içi sabit-pencere rate limiter. Tek proses
için yeterlidir; birden fazla worker/instance ile çalışan bir dağıtımda
Redis tabanlı bir çözüme (örn. slowapi + redis) geçilmelidir.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request

from services.auth import get_current_user
from services.config import AUTH_RATE_LIMIT_PER_MINUTE, LLM_DAILY_LIMIT_PER_USER, RATE_LIMIT_PER_MINUTE

_WINDOW_SECONDS = 60.0
_hits: dict[str, deque] = defaultdict(deque)


def _client_key(request: Request, bucket: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{bucket}:{host}"


def _make_limiter(bucket: str, limit: int):
    """Belirli bir bucket ve limit için ayrı bir istek dedektörü üretir —
    örn. auth uçları genel API limitinden bağımsız kendi sayacını tutar."""

    async def _limiter(request: Request) -> None:
        key = _client_key(request, bucket)
        now = time.monotonic()
        q = _hits[key]

        while q and now - q[0] > _WINDOW_SECONDS:
            q.popleft()

        if len(q) >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Çok fazla istek — dakikada en fazla {limit} istek yapabilirsiniz.",
            )

        q.append(now)

    return _limiter


# Genel, pahalı endpoint'ler (LLM/embedding/PDF işleme) için.
rate_limit = _make_limiter("general", RATE_LIMIT_PER_MINUTE)

# Auth uçları (login/register/şifre değişimi) için — brute-force'a karşı
# daha sıkı, genel API trafiğinden ayrı bir sayaç.
auth_rate_limit = _make_limiter("auth", AUTH_RATE_LIMIT_PER_MINUTE)


_DAY_SECONDS = 24.0 * 60.0 * 60.0
_llm_hits: dict[str, deque] = defaultdict(deque)


async def llm_daily_limit(current_user: dict = Depends(get_current_user)) -> None:
    """LLM çağıran uçlar (PDF Chat, Proje Öneri) için kullanıcı başına
    günlük kota — OpenRouter çağrıları ücretli olduğundan genel dakikalık
    limitten ayrı, kullanıcı kimliğine göre (IP'ye göre değil) sayılır.

    Depends(get_current_user) burada parametre olarak tanımlı olduğundan
    FastAPI bunu aynı request içinde diğer Depends(get_current_user)
    kullanımlarıyla (endpoint'in kendisi dahil) cache'ler — ekstra DB
    sorgusu/decode olmaz.
    """
    key = str(current_user["sub"])
    now = time.monotonic()
    q = _llm_hits[key]

    while q and now - q[0] > _DAY_SECONDS:
        q.popleft()

    if len(q) >= LLM_DAILY_LIMIT_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Günlük LLM kullanım hakkınızı doldurdunuz "
                f"(günde en fazla {LLM_DAILY_LIMIT_PER_USER} kullanım). "
                "Yarın tekrar deneyebilirsiniz."
            ),
        )

    q.append(now)
