# -*- coding: utf-8 -*-
"""
services/llm/reranker.py
══════════════════════════
LLM tabanlı reranking — OpenRouter'da ayrı bir "rerank" API'si olmadığından
(sadece /chat/completions var), aynı chat-completion altyapısı
(openrouter_client, aynı retry/backoff mantığıyla) kullanılarak adayları
sorguya göre alaka sırasına sokan hafif bir çağrıdır.

Best-effort: herhangi bir hata/parse sorununda ORİJİNAL sıra korunur — hem
Proje Öneri hem PDF Chat, reranking olmadan da (embedding skoruyla) doğru
çalışabilmeli. Reranking sadece bir kalite iyileştirmesidir, sert bir
bağımlılık değildir.
"""

from __future__ import annotations

import json
import logging
import re

from services.config import RERANK_MODEL
from services.llm.openrouter_client import call_openrouter, openrouter_available

logger = logging.getLogger(__name__)

MAX_CANDIDATE_CHARS = 400   # her adayın prompt'a giren kısmının üst sınırı
_ORDER_RE = re.compile(r"\[[\d,\s]+\]")


def rerank(query: str, candidates: list[str], timeout: int = 30) -> list[int]:
    """
    candidates'ı `query`ye göre en alakalıdan en alakasıza sıralar.

    Döner: candidates listesindeki 0-tabanlı indekslerin yeni sırası
    (örn. [2, 0, 1] → en alakalı candidates[2], sonra candidates[0], ...).
    Boş/tek elemanlı listede, OpenRouter kapalıyken veya herhangi bir hata/
    parse sorununda orijinal sıra ([0, 1, 2, ...]) döner.
    """
    n = len(candidates)
    identity = list(range(n))
    if n <= 1 or not openrouter_available():
        return identity

    numbered = "\n".join(
        f"{i + 1}. {(c or '').strip()[:MAX_CANDIDATE_CHARS]}"
        for i, c in enumerate(candidates)
    )

    system = (
        "Sen bir arama sonucu sıralama (relevance ranking) asistanısın. "
        "Verilen sorguya göre adayları en alakalıdan en alakasıza doğru "
        "sırala. SADECE JSON dizi döndür, başka hiçbir açıklama yazma."
    )
    user = (
        f'Sorgu: "{query}"\n\n'
        f"Adaylar:\n{numbered}\n\n"
        f"SADECE şu formatta, adayların 1-tabanlı indekslerini alaka "
        f"sırasına göre (en alakalı önce) içeren bir JSON dizisi döndür — "
        f"TÜM {n} indeks tam olarak bir kez geçmeli:\n[3, 1, 2, ...]"
    )

    try:
        raw = call_openrouter(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max(64, n * 6),
            temperature=0.0,
            top_p=1.0,
            timeout=timeout,
            model=RERANK_MODEL,
        )
        order = _parse_order(raw, n)
        if order is not None:
            return order
        logger.warning("[Rerank] Yanıt beklenen formatta değildi, orijinal sıra korunuyor: %r", raw[:200])
    except Exception as exc:
        logger.warning("[Rerank] Başarısız, orijinal sıra korunuyor: %s", exc)

    return identity


def _parse_order(raw: str, n: int) -> list[int] | None:
    match = _ORDER_RE.search(raw)
    if not match:
        return None
    try:
        nums = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    if not isinstance(nums, list):
        return None
    try:
        zero_based = [int(x) - 1 for x in nums]
    except (TypeError, ValueError):
        return None
    if sorted(zero_based) != list(range(n)):
        return None
    return zero_based
