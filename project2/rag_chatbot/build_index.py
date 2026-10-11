"""
Build a FAISS vector index from policy documents.

Reads all .md files from data/policies/, chunks them, embeds via OpenAI API,
and saves the FAISS index + chunk metadata to faiss_index/.

Usage:
    python build_index.py
"""
import os
import pickle
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
import faiss

load_dotenv()

POLICIES_DIR = os.path.join(os.path.dirname(__file__), "data", "policies")
INDEX_DIR = os.path.join(os.path.dirname(__file__), "faiss_index")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
EMBEDDING_MODEL = "text-embedding-3-small"


def load_documents(directory):
    """Read all .md files and return list of (filename, content)."""
    docs = []
    for fname in sorted(os.listdir(directory)):
        if fname.endswith(".md"):
            path = os.path.join(directory, fname)
            with open(path, "r") as f:
                docs.append((fname, f.read()))
    return docs


def chunk_text(text, source, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks with source metadata."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append({"text": chunk, "source": source, "start": start})
        start += chunk_size - overlap
    return chunks


def embed_texts(texts, client):
    """Embed a list of texts using OpenAI API."""
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def main():
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )

    # Load and chunk documents
    docs = load_documents(POLICIES_DIR)
    all_chunks = []
    for fname, content in docs:
        chunks = chunk_text(content, source=fname)
        all_chunks.extend(chunks)
        print(f"  {fname}: {len(chunks)} chunks")

    print(f"\nTotal chunks: {len(all_chunks)}")

    # Embed all chunks
    texts = [c["text"] for c in all_chunks]
    print("Embedding chunks...")
    embeddings = embed_texts(texts, client)
    embeddings_np = np.array(embeddings, dtype="float32")

    # Build FAISS index
    dim = embeddings_np.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings_np)
    print(f"FAISS index built: {index.ntotal} vectors, dim={dim}")

    # Save
    os.makedirs(INDEX_DIR, exist_ok=True)
    faiss.write_index(index, os.path.join(INDEX_DIR, "policy.index"))
    with open(os.path.join(INDEX_DIR, "chunks.pkl"), "wb") as f:
        pickle.dump(all_chunks, f)

    print(f"Index saved to {INDEX_DIR}/")


if __name__ == "__main__":
    main()
