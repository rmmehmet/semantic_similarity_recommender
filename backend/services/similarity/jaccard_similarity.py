from services.text_preprocessing import text_preprocessing

def _jaccard(s1, s2):
    """Calculates the Jaccard similarity between two sets of tokens.
    Parameters:
    s1 (set): The first set of tokens.
    s2 (set): The second set of tokens.
    Returns:
    float: The Jaccard similarity score."""

    inter = len(s1 & s2)
    union = len(s1 | s2)
    return inter / union if union > 0 else 0.0

def calculate_jaccard(documents):
    """Calculates the Jaccard similarity scores between all pairs of documents, returning the results in a structured format.
    Parameters:
    documents (list): A list of document dictionaries.
    Returns:
    list: A list of similarity results."""

    names = [doc["name"] for doc in documents]
    sets  = [set(text_preprocessing(doc["content"]).split()) for doc in documents]
    results = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            results.append({"doc1": names[i], "doc2": names[j], "score": float(_jaccard(sets[i], sets[j]))})
    return results

def calculate_jaccard_with_query(query_text, documents):
    """Calculates the Jaccard similarity scores between a query and a list of documents, returning the results in a structured format.
    Parameters:
    query_text (str): The query text.
    documents (list): A list of document dictionaries.
    Returns:
    list: A list of similarity results."""
    
    qset = set(text_preprocessing(query_text).split())
    return [
        {"name": doc["name"], "score": float(_jaccard(qset, set(text_preprocessing(doc["content"]).split())))}
        for doc in documents
    ]