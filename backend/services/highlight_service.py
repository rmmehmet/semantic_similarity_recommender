import base64
import re

import fitz
from sklearn.metrics.pairwise import cosine_similarity

from services.comparison_service import _pick

COLOR_IDENTICAL = (1.0, 0.45, 0.0)
COLOR_SEMANTIC  = (1.0, 0.82, 0.0)


def _split_sentences(text: str) -> list[str]:
    raw = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in raw if len(s.strip()) > 25]


def _bert_sentence_pairs(text1: str, text2: str, threshold: float = 0.80, top_n: int = 60):
    from services.similarity.bert_similarity import get_model

    sents1 = _split_sentences(text1)
    sents2 = _split_sentences(text2)

    if not sents1 or not sents2:
        return []

    model = get_model()
    emb1  = model.encode(sents1, show_progress_bar=False, normalize_embeddings=True)
    emb2  = model.encode(sents2, show_progress_bar=False, normalize_embeddings=True)
    sim   = cosine_similarity(emb1, emb2)

    pairs, used1, used2 = [], set(), set()
    flat = sorted(
        [(sim[i, j], i, j) for i in range(len(sents1)) for j in range(len(sents2))],
        reverse=True,
    )
    for score, i, j in flat:
        if score < threshold:
            break
        if i in used1 or j in used2:
            continue
        pairs.append((sents1[i], sents2[j], float(score)))
        used1.add(i); used2.add(j)
        if len(pairs) >= top_n:
            break

    return pairs


def _annotate_page(page, sentences: list[str], color: tuple) -> None:
    for sent in sentences:
        sent = sent.strip()
        if not sent or len(sent) < 15:
            continue
        quads = page.search_for(sent, quads=True)
        if quads:
            for q in quads:
                a = page.add_highlight_annot(q)
                a.set_colors(stroke=color); a.update()
        else:
            words = sent.split()
            for k in range(0, max(1, len(words) - 5), 3):
                chunk = " ".join(words[k:k + 6])
                if len(chunk) < 12:
                    continue
                for q in page.search_for(chunk, quads=True):
                    a = page.add_highlight_annot(q)
                    a.set_colors(stroke=color); a.update()


def _highlight_two_tiers(file_bytes: bytes, tier1: list[str], tier2: list[str]) -> bytes:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for page in doc:
        _annotate_page(page, tier2, COLOR_SEMANTIC)
        _annotate_page(page, tier1, COLOR_IDENTICAL)
    result = doc.tobytes()
    doc.close()
    return result


async def run_compare_highlight(
    target_file,
    compare_file,
    search_type: str = "fulltext",
    top_words:   int = 60,
) -> dict:
    from services.text_preprocessing import (
        extract_full_text_from_pdf,
        extract_abstract_from_pdf,
        extract_title_from_pdf,
        preprocess_text,
    )

    target_bytes  = await target_file.read()
    compare_bytes = await compare_file.read()

    eftp = extract_full_text_from_pdf
    eafp = extract_abstract_from_pdf
    etfp = extract_title_from_pdf
    pt   = preprocess_text

    target_raw  = _pick(target_bytes,  search_type, eftp, eafp, etfp, pt)
    compare_raw = _pick(compare_bytes, search_type, eftp, eafp, etfp, pt)

    pairs = _bert_sentence_pairs(target_raw, compare_raw, threshold=0.80, top_n=top_words)

    identical_t, identical_c = [], []
    semantic_t,  semantic_c  = [], []

    for t_sent, c_sent, score in pairs:
        if score >= 0.95:
            identical_t.append(t_sent); identical_c.append(c_sent)
        else:
            semantic_t.append(t_sent);  semantic_c.append(c_sent)

    target_hl  = _highlight_two_tiers(target_bytes,  identical_t, semantic_t)
    compare_hl = _highlight_two_tiers(compare_bytes, identical_c, semantic_c)

    return {
        "success":           True,
        "sentence_pairs":    len(pairs),
        "identical_count":   len(identical_t),
        "semantic_count":    len(semantic_t),
        "target_sentences":  len(identical_t) + len(semantic_t),
        "compare_sentences": len(identical_c) + len(semantic_c),
        "sample_pairs":      [(t[:90], c[:90], round(s, 3)) for t, c, s in pairs[:5]],
        "target_pdf":        base64.b64encode(target_hl).decode(),
        "compare_pdf":       base64.b64encode(compare_hl).decode(),
    }