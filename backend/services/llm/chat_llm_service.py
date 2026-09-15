# -*- coding: utf-8 -*-
"""
services/llm/chat_llm_service.py
══════════════════════════════════
PDF Sohbet özelliği için OpenRouter /chat/completions çağrısı
(OpenAI-uyumlu uç nokta). llm_suggestion_service.py'deki
_call_openrouter'dan farkı: JSON değil serbest metin döner ve çok turlu
(system + history + user) mesaj listesi kabul eder.
"""

from __future__ import annotations

import json
import logging
import urllib.request

from services.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL

logger = logging.getLogger(__name__)


def ollama_available() -> bool:
    return bool(OPENROUTER_API_KEY)


def call_ollama_chat(messages: list[dict], timeout: int = 180) -> str:
    """
    messages: [{"role": "system"|"user"|"assistant", "content": "..."}, ...]
    Senkron (bloklayan) bir ağ çağrısıdır — çağıran taraf run_in_executor
    ile thread pool'a taşımalıdır (bkz. services/chat_service.py).
    """
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY ayarlanmamış")

    payload = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": 0.4,
        "top_p":       0.9,
        "max_tokens":  1600,
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
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
