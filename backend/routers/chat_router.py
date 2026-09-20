# -*- coding: utf-8 -*-
"""
routers/chat_router.py
════════════════════════
PDF Sohbet — kullanıcının kendi yüklediği belgelerle (seçerek veya
seçmeden/genel) sohbet etmesini sağlar. Sohbetler kalıcıdır (Postgres):
her kullanıcının birden fazla sohbeti olabilir, listelenebilir, açılıp
kapanabilir ve silinebilir — ChatGPT'deki "yeni sohbet" akışına benzer.

POST /chat/message
  body: { message, pdf_names?: string[], conversation_id?: int|null }
  → { success, reply, sources, conversation_id, title? }
  Tüm yanıtı bekleyip tek seferde döner.

POST /chat/message/stream
  Aynı body — ama Server-Sent-Events (text/event-stream) ile yanıtı parça
  parça akıtır:
    event: chunk   data: {"delta": "..."}         (0+ kez)
    event: error   data: {"message": "..."}        (0 veya 1 kez)
    event: done     data: {"conversation_id", "sources", "title"?}  (her zaman en son)
  conversation_id verilmezse yeni bir sohbet oluşturulur (done'da title döner).

GET    /chat/conversations              → { conversations: [{id, title, updated_at}] }
GET    /chat/conversations/{id}         → { id, title, pdf_names, messages }
DELETE /chat/conversations/{id}         → { success }
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.auth import get_current_user
from services.chat_service import run_chat, stream_chat
from services.database.postgres_service import (
    pg_add_message,
    pg_create_conversation,
    pg_delete_conversation,
    pg_get_conversation,
    pg_get_conversation_messages,
    pg_list_conversations,
    pg_touch_conversation,
)
from services.rate_limit import llm_daily_limit, rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])

_MONTHS_TR = [
    "Oca", "Şub", "Mar", "Nis", "May", "Haz",
    "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara",
]


def _generate_title(pdf_names: list[str]) -> str:
    now = datetime.now()
    stamp = f"{now.day} {_MONTHS_TR[now.month - 1]} {now.strftime('%H:%M')}"
    suffix = pdf_names[0] if pdf_names else "Genel Sohbet"
    return f"{stamp} — {suffix}"


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _resolve_conversation(
    user_id: int, conversation_id: int | None, pdf_names: list[str]
) -> tuple[int, str | None, bool]:
    """
    conversation_id verilmişse sahiplik doğrular ve kapsamı (pdf_names) günceller.
    Verilmemişse yeni bir sohbet oluşturur.
    Döner: (conversation_id, yeni_başlık_veya_None, yeni_oluşturuldu_mu)
    """
    if conversation_id is not None:
        existing = await pg_get_conversation(conversation_id, user_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Sohbet bulunamadı")
        await pg_touch_conversation(conversation_id, pdf_names)
        return conversation_id, None, False

    new_title = _generate_title(pdf_names)
    created = await pg_create_conversation(user_id, new_title, pdf_names)
    return created["id"], new_title, True


class ChatRequest(BaseModel):
    message:         str = Field(..., min_length=1, max_length=4000)
    pdf_names:       list[str] = Field(default_factory=list)
    conversation_id: int | None = None


@router.post("/message", dependencies=[Depends(rate_limit), Depends(llm_daily_limit)])
async def chat_message(body: ChatRequest, current_user: dict = Depends(get_current_user)):
    user_id   = int(current_user["sub"])
    pdf_names = [n.strip() for n in body.pdf_names if n.strip()]
    message   = body.message.strip()

    conversation_id, new_title, created_new = await _resolve_conversation(
        user_id, body.conversation_id, pdf_names
    )

    result = await run_chat(
        user_id=user_id,
        message=message,
        pdf_names=pdf_names,
        conversation_id=conversation_id,
    )

    if result.get("success"):
        await pg_add_message(conversation_id, "user", message, [])
        await pg_add_message(conversation_id, "assistant", result.get("reply", ""), result.get("sources", []))
        result["conversation_id"] = conversation_id
        if new_title:
            result["title"] = new_title
    else:
        # Boş kalan (mesajsız) bir sohbet listede çöp olarak kalmasın.
        if created_new:
            await pg_delete_conversation(conversation_id, user_id)
            result["conversation_id"] = None
        else:
            result["conversation_id"] = conversation_id

    return result


@router.post("/message/stream", dependencies=[Depends(rate_limit), Depends(llm_daily_limit)])
async def chat_message_stream(body: ChatRequest, current_user: dict = Depends(get_current_user)):
    user_id   = int(current_user["sub"])
    pdf_names = [n.strip() for n in body.pdf_names if n.strip()]
    message   = body.message.strip()

    conversation_id, new_title, created_new = await _resolve_conversation(
        user_id, body.conversation_id, pdf_names
    )

    async def event_stream():
        full_reply = ""
        sources: list[dict] = []
        ok = False
        try:
            async for event in stream_chat(user_id, message, pdf_names, conversation_id):
                etype = event["type"]
                if etype == "chunk":
                    yield _sse("chunk", {"delta": event["delta"]})
                elif etype == "done":
                    full_reply = event["reply"]
                    sources    = event["sources"]
                    ok = True
                elif etype == "error":
                    yield _sse("error", {"message": event["message"]})
        except Exception:
            logger.exception("[Chat/stream] beklenmeyen hata (user=%s)", user_id)
            yield _sse("error", {"message": "Beklenmeyen bir hata oluştu."})

        if ok:
            await pg_add_message(conversation_id, "user", message, [])
            await pg_add_message(conversation_id, "assistant", full_reply, sources)
            payload: dict = {"conversation_id": conversation_id, "sources": sources}
            if new_title:
                payload["title"] = new_title
            yield _sse("done", payload)
        else:
            # Boş kalan (mesajsız) bir sohbet listede çöp olarak kalmasın.
            if created_new:
                await pg_delete_conversation(conversation_id, user_id)
            yield _sse("done", {"conversation_id": None})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations")
async def list_conversations(current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    rows = await pg_list_conversations(user_id)
    return {
        "conversations": [
            {
                "id":         r["id"],
                "title":      r["title"],
                "updated_at": r["updated_at"].astimezone(timezone.utc).isoformat() if r["updated_at"] else None,
            }
            for r in rows
        ]
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: int, current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    conv = await pg_get_conversation(conversation_id, user_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Sohbet bulunamadı")

    messages = await pg_get_conversation_messages(conversation_id)
    return {
        "id":        conv["id"],
        "title":     conv["title"],
        "pdf_names": conv["pdf_names"],
        "messages": [
            {
                "role":       m["role"],
                "content":    m["content"],
                "sources":    m["sources"],
                "created_at": m["created_at"].astimezone(timezone.utc).isoformat() if m["created_at"] else None,
            }
            for m in messages
        ],
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    deleted = await pg_delete_conversation(conversation_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Sohbet bulunamadı")
    return {"success": True}
