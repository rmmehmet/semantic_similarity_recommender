import Levenshtein
from services.text_preprocessing import text_preprocessing

def _norm(dist, l1, l2):
    """Normalizes the Levenshtein distance to a similarity score between 0 and 1, where 1 indicates identical strings and 0 indicates completely different strings.
    Parameters:
    dist (int): The Levenshtein distance.
    l1 (int): The length of the first string.
    l2 (int): The length of the second string.
    Returns:
    float: The normalized similarity score."""

    m = max(l1, l2)
    return 1 - (dist / m) if m > 0 else 1.0

def calculate_levenshtein(documents):
    """Calculates the Levenshtein similarity scores between all pairs of documents, returning the results in a structured format.
    Parameters:
    documents (list): A list of document dictionaries.
    Returns:
    list: A list of similarity results."""

    names = [doc["name"] for doc in documents]
    texts = [text_preprocessing(doc["content"]) for doc in documents]
    results = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            d = Levenshtein.distance(texts[i], texts[j])
            results.append({"doc1": names[i], "doc2": names[j], "score": float(_norm(d, len(texts[i]), len(texts[j])))})
    return results

def calculate_levenshtein_with_query(query_text, documents):
    """Calculates the Levenshtein similarity scores between a query and a list of documents, returning the results in a structured format.
    Parameters:
    query_text (str): The query text.
    documents (list): A list of document dictionaries.
    Returns:
    list: A list of similarity results."""

    pq = text_preprocessing(query_text)
    results = []
    for doc in documents:
        pd = text_preprocessing(doc["content"])
        d  = Levenshtein.distance(pq, pd)
        results.append({"name": doc["name"], "score": float(_norm(d, len(pq), len(pd)))})
    return results