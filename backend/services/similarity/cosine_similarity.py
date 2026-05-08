from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from services.text_preprocessing import text_preprocessing

def calculate_cosine(documents):
    texts = [text_preprocessing(doc["content"]) for doc in documents]
    names = [doc["name"] for doc in documents]
    vectorizer = CountVectorizer()
    vectors = vectorizer.fit_transform(texts)
    sim_matrix = cosine_similarity(vectors)
    results = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            results.append({"doc1": names[i], "doc2": names[j], "score": float(sim_matrix[i][j])})
    return results

def calculate_cosine_with_query(query_text, documents):
    processed_query = text_preprocessing(query_text)
    processed_docs  = [text_preprocessing(doc["content"]) for doc in documents]
    texts = [processed_query] + processed_docs
    vectorizer = CountVectorizer()
    vectors    = vectorizer.fit_transform(texts)
    sims = cosine_similarity(vectors[0:1], vectors[1:])[0]
    return [{"name": doc["name"], "score": float(sims[i])} for i, doc in enumerate(documents)]