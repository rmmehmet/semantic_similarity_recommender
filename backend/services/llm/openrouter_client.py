# -*- coding: utf-8 -*-
"""
services/llm/openrouter_client.py
══════════════════════════════════
OpenRouter /chat/completions için tek, paylaşılan senkron istemci.
llm_suggestion_service.py ve chat_llm_service.py bu modülü kullanır —
böylece istek gövdesi, hata sınıflandırması ve yeniden deneme mantığı
tek yerde tutulur.

Yeniden deneme: sadece GEÇİCİ hatalarda (ağ hatası/timeout, 429, 5xx)
yapılır — 400/401/403 gibi istemci hatalarında tekrar denemek sonucu
değiştirmez, doğrudan hata fırlatılır.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

from services.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL

logger = logging.getLogger(__name__)

_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (1, 3)  # deneme 1→2 ve 2→3 arası bekleme


def openrouter_available() -> bool:
    """OPENROUTER_API_KEY .env'de ayarlanmış mı kontrol eder."""
    return bool(OPENROUTER_API_KEY)


def call_openrouter(
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout: int,
) -> str:
    """
    messages: [{"role": "system"|"user"|"assistant", "content": "..."}, ...]
    Senkron (bloklayan) bir ağ çağrısıdır — çağıran taraf run_in_executor
    ile thread pool'a taşımalıdır.
    """
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY ayarlanmamış")

    payload = json.dumps({
        "model":       OPENROUTER_MODEL,
        "messages":    messages,
        "temperature": temperature,
        "top_p":       top_p,
        "max_tokens":  max_tokens,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        },
        method="POST",
    )

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as exc:
            if exc.code not in _RETRYABLE_HTTP_CODES or attempt == _MAX_ATTEMPTS:
                raise
            last_exc = exc
        except (urllib.error.URLError, TimeoutError) as exc:
            # TimeoutError ayrı yakalanır — bir okuma zaman aşımı urllib
            # tarafından URLError'a sarılmadan doğrudan fırlatılabilir.
            if attempt == _MAX_ATTEMPTS:
                raise
            last_exc = exc

        wait = _BACKOFF_SECONDS[min(attempt - 1, len(_BACKOFF_SECONDS) - 1)]
        logger.warning(
            "[OpenRouter] Deneme %d/%d başarısız (%s) — %ss sonra tekrar denenecek",
            attempt, _MAX_ATTEMPTS, last_exc, wait,
        )
        time.sleep(wait)

    # Buraya asla ulaşılmaz (son denemede raise edilir) — mypy/okunabilirlik için.
    raise last_exc  # type: ignore[misc]
