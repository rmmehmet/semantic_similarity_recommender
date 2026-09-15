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
değiştirmez, doğrudan hata fırlatılır. Streaming'de (stream_openrouter)
bu retry SADECE bağlantı kurulana kadar geçerlidir — akış başladıktan
sonra kopma olursa tekrar denenmez (kısmi metin zaten çağırana
iletilmiş olabilir), hata olduğu gibi yukarı fırlatılır.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Iterator

from services.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL

logger = logging.getLogger(__name__)

_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (1, 3)  # deneme 1→2 ve 2→3 arası bekleme


def openrouter_available() -> bool:
    """OPENROUTER_API_KEY .env'de ayarlanmış mı kontrol eder."""
    return bool(OPENROUTER_API_KEY)


def _build_request(payload: dict, stream: bool) -> urllib.request.Request:
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    }
    if stream:
        headers["Accept"] = "text/event-stream"
    return urllib.request.Request(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        data=data,
        headers=headers,
        method="POST",
    )


def _open_with_retry(req: urllib.request.Request, timeout: int):
    """
    Bağlantıyı açar (urlopen) — 429/5xx/ağ hatası/timeout'ta _MAX_ATTEMPTS'e
    kadar backoff'lu tekrar dener. Başarılı olursa açık response nesnesini
    döner; çağıran taraf onu okumaktan (ve kapatmaktan) sorumludur.
    """
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
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

    raise last_exc  # type: ignore[misc]  # döngü her zaman return ya da raise ile biter


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
    ile thread pool'a taşımalıdır. Tüm yanıtı bekler, tek parça döner.
    """
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY ayarlanmamış")

    req = _build_request({
        "model":       OPENROUTER_MODEL,
        "messages":    messages,
        "temperature": temperature,
        "top_p":       top_p,
        "max_tokens":  max_tokens,
    }, stream=False)

    with _open_with_retry(req, timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()


def stream_openrouter(
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout: int,
) -> Iterator[str]:
    """
    call_openrouter ile aynı, ama yanıtı OpenRouter'ın SSE akışından
    (`stream: true`) parça parça (delta metin) yield eder.

    Senkron (bloklayan) bir GENERATOR'dır — çağıran taraf bunu bir thread'de
    tüketip parçaları asyncio.Queue üzerinden async tarafa köprülemelidir
    (bkz. services/chat_service.py::stream_chat).
    """
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY ayarlanmamış")

    req = _build_request({
        "model":       OPENROUTER_MODEL,
        "messages":    messages,
        "temperature": temperature,
        "top_p":       top_p,
        "max_tokens":  max_tokens,
        "stream":      True,
    }, stream=True)

    resp = _open_with_retry(req, timeout)
    try:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line or line.startswith(":"):
                continue  # boş satır / keep-alive yorum satırı
            if not line.startswith("data:"):
                continue
            data_str = line[len("data:"):].strip()
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                logger.warning("[OpenRouter] Akış satırı parse edilemedi: %r", data_str[:200])
                continue
            choices = chunk.get("choices") or []
            delta = (choices[0].get("delta") or {}).get("content") if choices else None
            if delta:
                yield delta
    finally:
        resp.close()
