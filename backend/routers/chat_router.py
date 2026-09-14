# -*- coding: utf-8 -*-
"""
routers/chat_router.py
════════════════════════
PDF Sohbet — kullanıcının kendi yüklediği belgelerle (seçerek veya
seçmeden/genel) sohbet etmesini sağlayan tek endpoint.

POST /chat/message
  body: { message, pdf_names?: string[], history?: [{role, content}] }
  → { success, reply, sources: [{pdf_name, raw_title, score}] }
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from services.auth import get_current_user
from services.chat_service import run_chat
from services.rate_limit import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message:   str = Field(..., min_length=1, max_length=4000)
    pdf_names: list[str] = Field(default_factory=list)
    history:   list[ChatTurn] = Field(default_factory=list)


@router.post("/message", dependencies=[Depends(rate_limit)])
async def chat_message(body: ChatRequest, current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    result = await run_chat(
        user_id=user_id,
        message=body.message.strip(),
        pdf_names=[n.strip() for n in body.pdf_names if n.strip()],
        history=[t.model_dump() for t in body.history],
    )
    return result
