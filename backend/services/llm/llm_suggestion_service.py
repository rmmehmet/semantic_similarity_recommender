# -*- coding: utf-8 -*-
"""
services/llm/llm_suggestion_service.py
=======================================
Ollama API üzerinden Llama 3.1 Q4 çağrıları.

GPU kullanımını zorlamak için Ollama'yı şu şekilde başlat:
  OLLAMA_GPU_LAYERS=99 ollama serve          (Linux/Mac)
  set OLLAMA_GPU_LAYERS=99 && ollama serve   (Windows CMD)

İki dışa açık fonksiyon:
  - generate_topic_suggestion(input_text, search_type, similar_projects)
      → text modu: başlık / özet bazlı konu önerisi

  - generate_rag_analysis(pdf_full_text, pdf_title, similar_projects)
      → RAG modu: PDF tam metni + benzer chunk'lar ile derin analiz

Her ikisi de SENKRON çalışır.
suggest_service.py bunları run_in_executor ile thread pool'da çağırır.

Dönen sözlük Suggest.jsx LLMPanel bileşeniyle birebir uyumludur:
  mode, success, field, risk_level,
  analysis (text modu),
  similarity_analysis / original_aspects / improvement_suggestions (rag modu),
  topic_suggestions, revised_title
"""

import json
import urllib.request
import urllib.error
from typing import List, Dict, Any

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL    = "llama3.1:8b-instruct-q4_K_M"


# ──────────────────────────────────────────────────────────────────
# OLLAMA BAĞLANTI + ÇAĞRI
# ──────────────────────────────────────────────────────────────────

def _ollama_available() -> bool:
    """Ollama'nın ayakta olup olmadığını kontrol eder (3 sn timeout)."""
    try:
        req = urllib.request.urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return req.status == 200
    except Exception:
        return False


def _call_ollama(system: str, user: str) -> str:
    """
    Ollama /api/chat endpoint'ini çağırır (stream=False).
    GPU katmanları num_gpu=99 ile tamamen GPU'ya taşınır.
    """
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "stream": False,
        "options": {
            "temperature":    0.75,
            "top_p":          0.92,
            "repeat_penalty": 1.1,
            "num_predict":    1400,
            "num_gpu":        99,   # tüm katmanları GPU'ya gönder
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:  # 5 dakika
        data = json.loads(resp.read().decode("utf-8"))
        return data["message"]["content"].strip()


# ══════════════════════════════════════════════════════════════════
# TEXT MODU  —  başlık / özet araması
# ══════════════════════════════════════════════════════════════════

def generate_topic_suggestion(
    input_text       : str,
    search_type      : str,       # "title" | "abstract" | "fulltext"
    similar_projects : List[Dict],
) -> Dict[str, Any]:
    """
    Benzer projeler listesine bakarak özgün konu önerisi üretir.

    similar_projects her eleman:
      { score, pdf_name, raw_title, book_name, year, matched_text }

    Döner (Suggest.jsx text-mod beklentisi):
      { success, mode:"text", field, analysis, risk_level,
        topic_suggestions:[{title,rationale,novelty_score}],
        revised_title }
    """
    if not _ollama_available():
        return _err(
            "Ollama bulunamadı",
            "Ollama çalışmıyor. Windows'ta sistem tepsisinde Ollama ikonunu kontrol et.",
        )

    # Yüksek benzerlik projeleri önce al, yoksa ilk 3
    high = [p for p in similar_projects if p.get("score", 0) >= 0.80]
    high = high if high else similar_projects[:3]

    system, user = _build_suggest_messages(input_text, search_type, high)

    try:
        print(f"[LLM] Ollama çağrılıyor (text modu) — {OLLAMA_MODEL}")
        raw    = _call_ollama(system, user)
        parsed = _parse_json(raw)
        print("[LLM] ✓ Text yanıtı alındı")
        return {
            "success":          True,
            "mode":             "text",
            "field":            str(parsed.get("field", "")),
            "analysis":         str(parsed.get("analysis", "")),
            "risk_level":       str(parsed.get("risk_level", "yüksek")),
            "topic_suggestions": _safe_list(parsed.get("topic_suggestions")),
            "revised_title":    parsed.get("revised_title", ""),
        }
    except urllib.error.URLError as e:
        return _err(str(e), "Ollama'ya bağlanılamadı.")
    except Exception as e:
        return _err(str(e), f"LLM hatası: {type(e).__name__}")


# ══════════════════════════════════════════════════════════════════
# RAG MODU  —  PDF / tam metin araması
# ══════════════════════════════════════════════════════════════════

def generate_rag_analysis(
    pdf_full_text    : str,
    pdf_title        : str,
    similar_projects : List[Dict],
) -> Dict[str, Any]:
    """
    Yüklenen PDF'nin tam metni + benzer projelerin chunk'ları ile derin analiz.

    similar_projects her eleman:
      { score, pdf_name, raw_title, book_name, year, matched_text }

    Döner (Suggest.jsx rag-mod beklentisi):
      { success, mode:"rag", field, risk_level,
        similarity_analysis, original_aspects,
        improvement_suggestions, topic_suggestions, revised_title }
    """
    if not _ollama_available():
        return _err(
            "Ollama bulunamadı",
            "Ollama çalışmıyor. Windows'ta sistem tepsisinden Ollama'yı başlat.",
        )

    high = [p for p in similar_projects if p.get("score", 0) >= 0.80]
    high = high if high else similar_projects[:4]

    system, user = _build_rag_messages(pdf_full_text, pdf_title, high)

    try:
        print(f"[LLM] Ollama çağrılıyor (RAG modu) — {OLLAMA_MODEL}")
        raw    = _call_ollama(system, user)
        parsed = _parse_json(raw)
        print("[LLM] ✓ RAG yanıtı alındı")
        return {
            "success":                 True,
            "mode":                    "rag",
            "field":                   str(parsed.get("field", "")),
            "risk_level":              str(parsed.get("risk_level", "yüksek")),
            "similarity_analysis":     str(parsed.get("similarity_analysis", "")),
            "original_aspects":        _safe_list(parsed.get("original_aspects")),
            "improvement_suggestions": _safe_list(parsed.get("improvement_suggestions")),
            "topic_suggestions":       _safe_list(parsed.get("topic_suggestions")),
            "revised_title":           parsed.get("revised_title", ""),
        }
    except urllib.error.URLError as e:
        return _err(str(e), "Ollama'ya bağlanılamadı.")
    except Exception as e:
        return _err(str(e), f"LLM hatası: {type(e).__name__}")


# ══════════════════════════════════════════════════════════════════
# PROMPT OLUŞTURMA
# ══════════════════════════════════════════════════════════════════

def _build_suggest_messages(
    text       : str,
    search_type: str,
    similar    : List[Dict],
):
    label = {
        "title":    "Başlık",
        "abstract": "Özet",
        "fulltext": "Tam Metin",
    }.get(search_type, "Metin")

    benzer_list = "\n".join(
        f'  {i+1}. "{p.get("raw_title") or p.get("pdf_name","?")}"'
        f' — %{round(p.get("score", 0) * 100, 1)}'
        f'  [{p.get("book_name","")}'
        f' {p.get("year","") or ""}]'
        for i, p in enumerate(similar)
    )

    system = (
        "Sen LIFT UP akademik proje değerlendirme asistanısın. "
        "Kullanıcının projesi mevcut çalışmalarla yüksek benzerlik gösteriyor. "
        "AYNI alanda FARKLI ve ÖZGÜN alt konular öner. Türkçe yaz. "
        "SADECE JSON döndür. Başka hiçbir şey yazma."
    )

    user = f"""Kullanıcı Projesi ({label}):
\"\"\"{text[:900]}\"\"\"

Benzer projeler (veritabanından):
{benzer_list}

SADECE aşağıdaki JSON formatını döndür:
{{
  "field": "Araştırma alanı",
  "analysis": "Projenin mevcut çalışmalarla benzerlik analizi — 2-3 cümle",
  "risk_level": "yüksek",
  "topic_suggestions": [
    {{"title": "Özgün öneri 1", "rationale": "Neden bu konu farklı ve değerli", "novelty_score": 88}},
    {{"title": "Özgün öneri 2", "rationale": "Neden bu konu farklı ve değerli", "novelty_score": 81}},
    {{"title": "Özgün öneri 3", "rationale": "Neden bu konu farklı ve değerli", "novelty_score": 75}}
  ],
  "revised_title": "Kullanıcının başlığını özgünleştiren alternatif"
}}"""

    return system, user


def _build_rag_messages(
    pdf_text : str,
    pdf_title: str,
    similar  : List[Dict],
):
    # Tüm PDF metni ve matched_text'lerin tamamı gönderilir — karakter kısıtı yok
    context_blocks = []
    for i, p in enumerate(similar[:4]):
        matched = p.get("matched_text") or ""
        context_blocks.append(
            f'[Kaynak {i+1}] '
            f'"{p.get("raw_title") or p.get("pdf_name","?")}"\n'
            f'Benzerlik: %{round(p.get("score", 0) * 100, 1)}\n'
            f'İçerik: {matched}'
        )
    context = "\n\n".join(context_blocks) if context_blocks else "— bağlam yok —"

    system = (
        "Sen LIFT UP akademik proje analiz uzmanısın. "
        "Kullanıcının PDF'ini ve veritabanındaki benzer projelerin chunk'larını "
        "kullanarak derin ve yapıcı bir akademik analiz yap. "
        "Türkçe yaz. SADECE JSON döndür. Başka hiçbir şey yazma."
    )

    user = f"""ANALİZ EDİLECEK PROJE:
Başlık: {pdf_title}

Proje İçeriği (tam metin):
\"\"\"{pdf_text}\"\"\"

VERİTABANINDAKİ BENZER PROJELER — RAG Context:
{context}

Yukarıdaki projeyi benzer çalışmalarla karşılaştırarak derin analiz yap.

SADECE aşağıdaki JSON formatını döndür:
{{
  "field": "Araştırma alanı",
  "risk_level": "yüksek|orta|düşük",
  "similarity_analysis": "Hangi yönleri benzer, neden — 2-3 cümle",
  "original_aspects": [
    "Bu projede özgün olan yön 1",
    "Bu projede özgün olan yön 2",
    "Bu projede özgün olan yön 3"
  ],
  "improvement_suggestions": [
    "Projeyi güçlendirecek öneri 1",
    "Projeyi güçlendirecek öneri 2",
    "Projeyi güçlendirecek öneri 3"
  ],
  "topic_suggestions": [
    {{"title": "Alternatif konu 1", "rationale": "Neden daha özgün", "novelty_score": 90}},
    {{"title": "Alternatif konu 2", "rationale": "Neden daha özgün", "novelty_score": 83}},
    {{"title": "Alternatif konu 3", "rationale": "Neden daha özgün", "novelty_score": 76}}
  ],
  "revised_title": "Özgünleştirilmiş başlık önerisi"
}}"""

    return system, user


# ══════════════════════════════════════════════════════════════════
# YARDIMCILAR
# ══════════════════════════════════════════════════════════════════

def _parse_json(raw: str) -> Dict:
    """
    LLM çıktısından JSON bloğunu çıkarır.
    Önce ```json...``` bloğu, sonra ilk { ... } denenir.
    """
    # ``` blokları temizle
    clean = raw.replace("```json", "").replace("```", "").strip()

    s = clean.find("{")
    e = clean.rfind("}") + 1
    if s != -1 and e > s:
        try:
            return json.loads(clean[s:e])
        except json.JSONDecodeError:
            pass

    # Son çare: ham yanıtı analysis alanına koy
    return {
        "field":            "",
        "analysis":         clean[:400] or "Analiz yapılamadı.",
        "similarity_analysis": clean[:400] or "Analiz yapılamadı.",
        "risk_level":       "yüksek",
        "topic_suggestions": [],
        "original_aspects":  [],
        "improvement_suggestions": [],
        "revised_title":    "",
    }


def _safe_list(val: Any) -> list:
    """LLM çıktısı list değilse güvenli boş liste döner."""
    return val if isinstance(val, list) else []


def _err(err_str: str, msg: str) -> Dict:
    return {
        "success":           False,
        "mode":              "text",
        "error":             err_str,
        "analysis":          msg,
        "similarity_analysis": msg,
        "field":             "",
        "risk_level":        "yüksek",
        "topic_suggestions": [],
        "original_aspects":  [],
        "improvement_suggestions": [],
        "revised_title":     "",
    }