"""
scripts/build_faiss_index.py
Phase 4 (Add Knowledge & Retrieval) - step 2: embed all chunks and build/save
the vector index to knowledge/faiss_index/{index.faiss,index.pkl} plus the
fitted embedder state (embedder_state.pkl) so queries use the same vector
space at query time.

Run:  python scripts/build_faiss_index.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from retrieval.chunker import Chunk
from retrieval.embedder import get_embedder, OfflineEmbedder
from retrieval.faiss_store import VectorStore

ROOT = os.path.join(os.path.dirname(__file__), "..")
CHUNKS_PATH = os.path.join(ROOT, "knowledge", "processed", "chunks.json")
INDEX_DIR = os.path.join(ROOT, "knowledge", "faiss_index")
EMBEDDER_STATE_PATH = os.path.join(INDEX_DIR, "embedder_state.pkl")


def main():
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        raw_chunks = json.load(f)
    chunks = [Chunk(**c) for c in raw_chunks]
    texts = [c.text for c in chunks]
    print(f"Embedding {len(texts)} chunks...")

    embedder = get_embedder()
    vectors = embedder.embed_documents(texts)
    print(f"Embedding matrix shape: {vectors.shape}")

    store = VectorStore()
    store.build(chunks, vectors)

    os.makedirs(INDEX_DIR, exist_ok=True)
    store.save(INDEX_DIR)
    print(f"Saved vector index to {INDEX_DIR}/index.faiss + index.pkl")

    if isinstance(embedder, OfflineEmbedder):
        embedder.save(EMBEDDER_STATE_PATH)
        print(f"Saved offline embedder state to {EMBEDDER_STATE_PATH}")


if __name__ == "__main__":
    main()
