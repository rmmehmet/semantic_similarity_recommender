import asyncio
import logging
from functools import partial

from fastapi import HTTPException

from services.upload_validation import validate_pdf_bytes

logger = logging.getLogger(__name__)

THRESHOLDS = {
    "bert":        0.80,
    "cosine":      0.70,
    "tfidf":       0.70,
    "jaccard":     0.30,
    "levenshtein": 0.30,
}

def _pick(file_bytes: bytes, search_type: str, eftp, eafp, etfp, pt) -> str:
    """Extract and preprocess text based on the search type.
    Parameters:
        file_bytes (bytes): The bytes of the PDF file.
        search_type (str): The type of text to extract.
        eftp: Function to extract full text from PDF.
        eafp: Function to extract abstract from PDF.
        etfp: Function to extract title from PDF.
        pt: Function for text preprocessing.
    Returns:
        str: The extracted and preprocessed text.
    """

    if search_type == "title":    return pt(etfp(file_bytes))
    if search_type == "abstract": return pt(eafp(file_bytes))
    return pt(eftp(file_bytes))

def _combined(results: dict, docs: list) -> list:
    """Combine results from different algorithms and calculate average scores.
    Parameters:
        results (dict): A dictionary containing similarity scores from different algorithms.
        docs (list): A list of dictionaries containing document information.
    Returns:
        list: A list of dictionaries containing the combined results.
    """

    names = [d["name"] for d in docs]
    out = []
    for name in names:
        # Sadece başarıyla çalışan (sonuç üretmiş) algoritmalar ortalamaya dahil edilir;
        # aksi halde hatalı bir algoritma sessizce 0.0 gibi davranıp ortalamayı düşürürdü.
        algo_scores = {}
        failed_algos = []
        for algo, scores in results.items():
            match = next((s["score"] for s in scores if s["name"] == name), None)
            if match is None:
                failed_algos.append(algo)
            else:
                algo_scores[algo] = round(match, 4)

        avg = sum(algo_scores.values()) / len(algo_scores) if algo_scores else 0
        out.append({
            "name":          name,
            "average_score": round(avg, 4),
            "algo_scores":   algo_scores,
            "failed_algos":  failed_algos,
        })
    return sorted(out, key=lambda x: x["average_score"], reverse=True)

def _load_algos():
    """Load similarity algorithms from the services.similarity module.
    Returns:
        dict: A dictionary containing the loaded similarity algorithms.
    """

    from services.similarity.cosine_similarity      import calculate_cosine_with_query
    from services.similarity.jaccard_similarity     import calculate_jaccard_with_query
    from services.similarity.tfidf_similarity       import calculate_tfidf_with_query
    from services.similarity.levenshtein_similarity import calculate_levenshtein_with_query
    from services.similarity.bert_similarity        import calculate_bert_with_query
    return {
        "cosine":      calculate_cosine_with_query,
        "jaccard":     calculate_jaccard_with_query,
        "tfidf":       calculate_tfidf_with_query,
        "levenshtein": calculate_levenshtein_with_query,
        "bert":        calculate_bert_with_query,
    }

def _load_prep():
    """Load text preprocessing functions from the services.text_preprocessing module.
    Returns:
        tuple: A tuple containing the loaded preprocessing functions.
    """

    from services.text_preprocessing import (
        extract_full_text_from_pdf,
        extract_abstract_from_pdf,
        extract_title_from_pdf,
        text_preprocessing,
    )
    return extract_full_text_from_pdf, extract_abstract_from_pdf, extract_title_from_pdf, text_preprocessing

async def run_compare(target_file, compare_files, search_type: str) -> dict:
    eftp, eafp, etfp, pt = _load_prep()
    algos = _load_algos()
    loop = asyncio.get_running_loop()

    target_bytes = await target_file.read()
    validate_pdf_bytes(target_bytes, target_file.filename)
    target_content = _pick(target_bytes, search_type, eftp, eafp, etfp, pt)

    docs = []
    for f in compare_files:
        data = await f.read()
        validate_pdf_bytes(data, f.filename)
        docs.append({"name": f.filename, "content": _pick(data, search_type, eftp, eafp, etfp, pt)})

    if not docs:
        raise HTTPException(400, "No documents to compare.")

    results = {}
    for name, fn in algos.items():
        try:
            # BERT/TF-IDF gibi CPU-ağır algoritmalar event loop'u bloklamasın.
            scores = await loop.run_in_executor(None, partial(fn, target_content, docs))
            results[name] = [{"name": s["name"], "score": float(s["score"])} for s in scores[:10]]
        except Exception as e:
            results[name] = []
            logger.error("[Compare] %s algoritması hata verdi: %s", name, e)

    return {
        "success":     True,
        "target":      target_file.filename,
        "search_type": search_type,
        "results":     results,
        "combined":    _combined(results, docs)[:10],
        "thresholds":  THRESHOLDS,
    }