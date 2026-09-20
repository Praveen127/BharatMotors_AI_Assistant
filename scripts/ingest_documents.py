"""
scripts/ingest_documents.py
Phase 4 (Add Knowledge & Retrieval) - step 1: load PDFs from knowledge/raw/,
chunk them, and write knowledge/processed/chunks.json.

Run:  python scripts/ingest_documents.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from retrieval.document_loader import load_knowledge_dir
from retrieval.chunker import chunk_documents, chunks_to_json

ROOT = os.path.join(os.path.dirname(__file__), "..")
RAW_DIR = os.path.join(ROOT, "knowledge", "raw")
OUT_PATH = os.path.join(ROOT, "knowledge", "processed", "chunks.json")


def main():
    docs = load_knowledge_dir(RAW_DIR)
    print(f"Loaded {len(docs)} source documents: {[d.source for d in docs]}")

    chunks = chunk_documents(docs)
    print(f"Produced {len(chunks)} chunks (chunk_size=500, overlap=80).")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks_to_json(chunks), f, indent=2)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
