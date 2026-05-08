from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from services.text_preprocessing import text_preprocessing
import numpy as np

_model = None

def get_model():
    """Load and cache the BERT model for similarity calculations.
    Returns:
    SentenceTransformer: The loaded BERT model."""
    global _model
    if _model is None:
        _model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return _model


def _split(text, max_length=500, overlap=50):
    """Splits the input text into chunks of a specified maximum length with optional overlap, using a hierarchy of separators to maintain semantic coherence.
    Parameters:
    text (str): The input text to be split.
    max_length (int): The maximum length of each chunk.
    overlap (int): The amount of overlap between consecutive chunks.
    Returns:
    list: A list of text chunks."""
    separators = ["\n\n", "\n", ". ", " "]

    def _rec(text, seps):
        if len(text) <= max_length:
            return [text]
        if not seps:
            step = max_length - overlap
            return [text[i:i+max_length] for i in range(0, len(text), step)]
        sep = seps[0]
        parts = text.split(sep)
        chunks, current = [], ""
        for part in parts:
            if len(current) + len(part) <= max_length:
                current += part + sep
            else:
                if current:
                    chunks.extend(_rec(current.strip(), seps[1:]))
                current = part + sep
        if current:
            chunks.extend(_rec(current.strip(), seps[1:]))
        return chunks

    return _rec(text, separators)

def calculate_bert_with_query(query_text, documents):
    """Calculates the BERT similarity scores between a query and a list of documents, returning the results sorted by relevance.
    Parameters:
    query_text (str): The query text.
    documents (list): A list of document dictionaries.
    Returns:
    list: A list of similarity results sorted by relevance."""
    model = get_model()
    processed_query = text_preprocessing(query_text)
    query_emb = model.encode([processed_query], show_progress_bar=False, normalize_embeddings=True)

    results = []
    for doc in documents:
        processed_doc = text_preprocessing(doc["content"])
        chunks = _split(processed_doc)
        if not chunks:
            results.append({"name": doc["name"], "score": 0.0})
            continue
        chunk_embs = model.encode(chunks, show_progress_bar=False, normalize_embeddings=True)
        sims = cosine_similarity(query_emb, chunk_embs)[0]
        results.append({"name": doc["name"], "score": float(np.max(sims))})

    return sorted(results, key=lambda x: x["score"], reverse=True)