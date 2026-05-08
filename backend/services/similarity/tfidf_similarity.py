from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from services.text_preprocessing import text_preprocessing

def calculate_tfidf(documents):
    """Calculates the TF-IDF similarity scores between all pairs of documents, returning the results in a structured format.
    Parameters:
    documents (list): A list of document dictionaries.
    Returns:
    list: A list of similarity results."""

    texts = [text_preprocessing(doc["content"]) for doc in documents]
    names = [doc["name"] for doc in documents]
    vec   = TfidfVectorizer(max_features=5000, ngram_range=(1, 2), min_df=2)
    mat   = vec.fit_transform(texts)
    sim   = cosine_similarity(mat)
    results = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            results.append({"doc1": names[i], "doc2": names[j], "score": float(sim[i][j])})
    return results

def calculate_tfidf_with_query(query_text, documents):
    """Calculates the TF-IDF similarity scores between a query and a list of documents, returning the results in a structured format.
    Parameters:
    query_text (str): The query text.
    documents (list): A list of document dictionaries.
    Returns:
    list: A list of similarity results."""

    processed_query = text_preprocessing(query_text)
    processed_docs  = [text_preprocessing(doc["content"]) for doc in documents]
    texts = [processed_query] + processed_docs
    vec   = TfidfVectorizer(max_features=1000, ngram_range=(1, 2), min_df=1)
    mat   = vec.fit_transform(texts)
    sims  = cosine_similarity(mat[0:1], mat[1:])[0]
    return [{"name": doc["name"], "score": float(sims[i])} for i, doc in enumerate(documents)]