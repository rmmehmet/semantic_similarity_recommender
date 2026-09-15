# -*- coding: utf-8 -*-
"""
services/llm/chat_llm_service.py
══════════════════════════════════
PDF Sohbet özelliği için OpenRouter /chat/completions çağrısı
(OpenAI-uyumlu uç nokta, openrouter_client üzerinden — bkz. o modül için
yeniden deneme/hata sınıflandırma mantığı). llm_suggestion_service.py'den
farkı: JSON değil serbest metin döner ve çok turlu (system + history +
user) mesaj listesi kabul eder.
"""

from __future__ import annotations

from typing import Iterator

from services.llm.openrouter_client import call_openrouter, openrouter_available, stream_openrouter


def ollama_available() -> bool:
    return openrouter_available()


def call_ollama_chat(messages: list[dict], timeout: int = 180) -> str:
    """
    messages: [{"role": "system"|"user"|"assistant", "content": "..."}, ...]
    Senkron (bloklayan) bir ağ çağrısıdır — çağıran taraf run_in_executor
    ile thread pool'a taşımalıdır (bkz. services/chat_service.py).
    """
    return call_openrouter(
        messages=messages,
        max_tokens=1600,
        temperature=0.4,
        top_p=0.9,
        timeout=timeout,
    )


def stream_ollama_chat(messages: list[dict], timeout: int = 180) -> Iterator[str]:
    """
    call_ollama_chat ile aynı, ama yanıtı parça parça (delta metin) yield eder.
    Senkron (bloklayan) bir GENERATOR'dır — bkz. services/chat_service.py::stream_chat.
    """
    return stream_openrouter(
        messages=messages,
        max_tokens=1600,
        temperature=0.4,
        top_p=0.9,
        timeout=timeout,
    )
