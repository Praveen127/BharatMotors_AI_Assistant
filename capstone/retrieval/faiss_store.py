"""
faiss_store.py
Vector index over knowledge chunks, saved/loaded as knowledge/faiss_index/
index.faiss (vectors) + index.pkl (chunk metadata + embedder state reference),
mirroring LangChain's `FAISS.save_local` / `FAISS.load_local` file layout.

If the `faiss` package is installed, it is used directly (production path).
Otherwise falls back to an exact cosine-similarity NumPy search, which is
correct (not approximate) at this knowledge base's scale (tens of chunks) --
documented in docs/engineering_justification.md.
"""
import os
import pickle
import numpy as np
from typing import List, Tuple
from retrieval.chunker import Chunk

try:
    import faiss  # type: ignore
    _HAS_FAISS = True
except ImportError:
    _HAS_FAISS = False


class VectorStore:
    def __init__(self):
        self.chunks: List[Chunk] = []
        self.vectors: np.ndarray = None
        self._faiss_index = None

    def build(self, chunks: List[Chunk], vectors: np.ndarray):
        self.chunks = chunks
        self.vectors = vectors.astype("float32")
        if _HAS_FAISS:
            index = faiss.IndexFlatIP(self.vectors.shape[1])
            index.add(self.vectors)
            self._faiss_index = index

    def search(self, query_vec: np.ndarray, k: int = 3) -> List[Tuple[Chunk, float]]:
        if self.vectors is None or len(self.chunks) == 0:
            return []
        q = query_vec.astype("float32")
        if _HAS_FAISS and self._faiss_index is not None:
            scores, idxs = self._faiss_index.search(q.reshape(1, -1), k)
            results = [(self.chunks[i], float(scores[0][j]))
                       for j, i in enumerate(idxs[0]) if i != -1]
            return results
        # NumPy fallback: cosine similarity (vectors are pre-normalized)
        sims = self.vectors @ q
        top_idx = np.argsort(-sims)[:k]
        return [(self.chunks[i], float(sims[i])) for i in top_idx]

    def save(self, dir_path: str):
        os.makedirs(dir_path, exist_ok=True)
        vec_path = os.path.join(dir_path, "index.faiss")
        meta_path = os.path.join(dir_path, "index.pkl")
        if _HAS_FAISS and self._faiss_index is not None:
            faiss.write_index(self._faiss_index, vec_path)
        else:
            with open(vec_path, "wb") as f:
                np.save(f, self.vectors)
        with open(meta_path, "wb") as f:
            pickle.dump({"chunks": self.chunks, "backend": "faiss" if _HAS_FAISS else "numpy"}, f)

    @classmethod
    def load(cls, dir_path: str) -> "VectorStore":
        vec_path = os.path.join(dir_path, "index.faiss")
        meta_path = os.path.join(dir_path, "index.pkl")
        with open(meta_path, "rb") as f:
            meta = pickle.load(f)
        store = cls()
        store.chunks = meta["chunks"]
        if meta["backend"] == "faiss" and _HAS_FAISS:
            store._faiss_index = faiss.read_index(vec_path)
        else:
            with open(vec_path, "rb") as f:
                store.vectors = np.load(f)
        return store
