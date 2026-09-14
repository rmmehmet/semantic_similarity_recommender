# -*- coding: utf-8 -*-
"""
services/llm/chat_llm_service.py
══════════════════════════════════
PDF Sohbet özelliği için Ollama /api/chat çağrısı. llm_suggestion_service.py'deki
_call_ollama'dan farkı: JSON değil serbest metin döner ve çok turlu (system +
history + user) mesaj listesi kabul eder.
"""

from __future__ import annotations

import json
import logging
import urllib.request

from services.config import OLLAMA_URL

logger = logging.getLogger(__name__)

CHAT_MODEL = "llama3.1:8b-instruct-q4_K_M"


def ollama_available() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def call_ollama_chat(messages: list[dict], timeout: int = 180) -> str:
    """
    messages: [{"role": "system"|"user"|"assistant", "content": "..."}, ...]
    Senkron (bloklayan) bir ağ çağrısıdır — çağıran taraf run_in_executor
    ile thread pool'a taşımalıdır (bkz. services/chat_service.py).
    """
    payload = json.dumps({
        "model": CHAT_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature":    0.4,
            "top_p":          0.9,
            "repeat_penalty": 1.1,
            "num_predict":    900,
            "num_gpu":        99,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["message"]["content"].strip()
