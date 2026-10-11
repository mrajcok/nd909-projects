"""
Load a persisted FAISS index and chunk metadata.

Usage:
    from load_index import load_index
    index, chunks = load_index()
"""
import os
import pickle
import faiss

INDEX_DIR = os.path.join(os.path.dirname(__file__), "faiss_index")


def load_index(index_dir=INDEX_DIR):
    """Load FAISS index and chunk metadata from disk."""
    index = faiss.read_index(os.path.join(index_dir, "policy.index"))
    with open(os.path.join(index_dir, "chunks.pkl"), "rb") as f:
        chunks = pickle.load(f)
    return index, chunks
