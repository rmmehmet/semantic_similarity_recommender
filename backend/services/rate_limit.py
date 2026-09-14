# -*- coding: utf-8 -*-
"""
services/rate_limit.py
════════════════════════
Pahalı endpoint'ler (LLM/embedding/PDF işleme) için basit, bellek-içi
sabit-pencere rate limiter. Tek proses için yeterlidir; birden fazla
worker/instance ile çalışan bir dağıtımda Redis tabanlı bir çözüme
(örn. slowapi + redis) geçilmelidir.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from services.config import RATE_LIMIT_PER_MINUTE

_WINDOW_SECONDS = 60.0
_hits: dict[str, deque] = defaultdict(deque)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def rate_limit(request: Request) -> None:
    key = _client_key(request)
    now = time.monotonic()
    q = _hits[key]

    while q and now - q[0] > _WINDOW_SECONDS:
        q.popleft()

    if len(q) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail=f"Çok fazla istek — dakikada en fazla {RATE_LIMIT_PER_MINUTE} istek yapabilirsiniz.",
        )

    q.append(now)
