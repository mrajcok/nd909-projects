"""
RAG pipeline: embed query → retrieve from FAISS → generate answer via LLM.

Usage:
    from rag import query_rag
    answer = query_rag("What is the meal expense limit?")
"""
import os
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
from load_index import load_index

load_dotenv()

EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = (
    "You are an expense policy assistant for FinanceGuard Inc. "
    "Answer employee questions using the provided policy context. "
    "Be helpful, accurate, and concise. "
    "If the answer is not in the context, say you don't know."
)

# Load index once at module level
_index, _chunks = load_index()

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
)


def embed_query(query):
    """Embed a query string and return numpy vector."""
    response = _client.embeddings.create(model=EMBEDDING_MODEL, input=[query])
    return np.array(response.data[0].embedding, dtype="float32").reshape(1, -1)


def retrieve(query, k=3):
    """Retrieve top-k chunks from FAISS index."""
    query_vec = embed_query(query)
    distances, indices = _index.search(query_vec, k)
    results = []
    for i, idx in enumerate(indices[0]):
        if idx < len(_chunks):
            results.append({
                "text": _chunks[idx]["text"],
                "source": _chunks[idx]["source"],
                "distance": float(distances[0][i]),
            })
    return results


def query_rag(question, k=3):
    """Full RAG pipeline: retrieve context, then generate answer."""
    retrieved = retrieve(question, k=k)

    context = "\n\n---\n\n".join(r["text"] for r in retrieved)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {question}",
        },
    ]

    response = _client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=500,
    )

    answer = response.choices[0].message.content
    sources = [r["source"] for r in retrieved]
    return {"answer": answer, "sources": sources}
