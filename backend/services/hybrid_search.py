# -*- coding: utf-8 -*-
"""
services/hybrid_search.py
════════════════════════════
Vektör (Milvus/semantik) ve anahtar kelime (Postgres full-text search/lexical)
arama sonuçlarını Reciprocal Rank Fusion (RRF) ile birleştirir.

Neden RRF: iki arama iki farklı, birbiriyle KARŞILAŞTIRILAMAZ skor ölçeği
üretir (Milvus cosine ~[0,1], Postgres ts_rank keyfi küçük bir değer) —
bunları normalize etmeye çalışmak kırılgandır. RRF skorları değil, her
listedeki SIRAYI kullanır: score = Σ 1/(k + rank). Bilgi erişiminde standart,
kanıtlanmış bir tekniktir.

ÖNEMLİ: fuse_hits() hit'lerin orijinal "score" alanına DOKUNMAZ — sadece
SIRALARINI belirler. Bunun nedeni: "score" alanı (Milvus cosine benzerliği)
suggest_service.py ve llm_suggestion_service.py'de "yüksek benzerlik" eşiği
(>= 0.80) için kullanılıyor; RRF skorlarıyla (tipik olarak <0.03) ezilirse bu
eşik anlamsızlaşır. Sadece anahtar kelime aramasında bulunan (vektör
aramasında hiç görünmeyen) bir hit'in gerçek bir cosine skoru yoktur — score
alanı boş bırakılır (çağıran taraf .get("score", 0.0) ile güvenle okur).
"""

from __future__ import annotations

RRF_K = 60  # bilgi erişiminde yaygın kullanılan standart sabit


def _hit_key(h: dict) -> str | None:
    pdf_name  = h.get("pdf_name")
    chunk_idx = h.get("chunk_idx")
    if not pdf_name or chunk_idx is None:
        return None
    return f"{pdf_name}::{chunk_idx}"


def fuse_hits(*ranked_lists: list[dict], k: int = RRF_K) -> list[dict]:
    """
    ranked_lists: her biri zaten en alakalıdan en alakasıza sıralı hit
    listesi (örn. Milvus sonucu, Postgres FTS sonucu). Her hit en az
    "pdf_name" ve "chunk_idx" taşımalıdır (kimlik anahtarı için).

    Döner: RRF skoruna göre azalan sıralı, tekilleştirilmiş hit listesi.
    Aynı chunk birden fazla listede geçiyorsa alanlar (text/section/...)
    birleştirilir (ilk görülen değer korunur, eksikler tamamlanır) — ama
    "score" alanı asla üzerine yazılmaz/taşınmaz.
    """
    by_key: dict[str, dict] = {}
    rrf: dict[str, float] = {}

    for ranked in ranked_lists:
        for rank, h in enumerate(ranked, start=1):
            key = _hit_key(h)
            if key is None:
                continue
            rrf[key] = rrf.get(key, 0.0) + 1.0 / (k + rank)

            if key not in by_key:
                by_key[key] = dict(h)  # "score" dahil, varsa olduğu gibi kopyalanır
            else:
                existing = by_key[key]
                for field in ("text", "section", "subsection", "page_start", "page_end"):
                    if not existing.get(field) and h.get(field):
                        existing[field] = h[field]
                # İlk kaynakta score yoktu ama bu kaynakta varsa (örn. önce
                # keyword, sonra vector listesi işlendi) devral.
                if "score" not in existing and "score" in h:
                    existing["score"] = h["score"]

    return [by_key[key] for key, _ in sorted(rrf.items(), key=lambda kv: -kv[1])]
