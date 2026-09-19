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

from fastapi import HTTPException, Request

from services.config import AUTH_RATE_LIMIT_PER_MINUTE, RATE_LIMIT_PER_MINUTE

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
