"""
retriever.py
High-level retrieval API used by the agent. Wraps VectorStore + embedder and
adds a *grounding threshold*: if the best match similarity is below
MIN_CONFIDENCE, the retriever reports "no confident match" instead of
returning a weak chunk. This is what lets the agent refuse to answer rather
than fabricate a policy (Scenario 3 safety requirement: "Must not fabricate
policies").
"""
import os
from dataclasses import dataclass
from typing import List
from retrieval.faiss_store import VectorStore
from retrieval.embedder import get_embedder

MIN_CONFIDENCE = 0.60  # cosine-similarity threshold for offline TF-IDF embeddings.
# Raised from an initial 0.12 during Phase 9 evaluation after TC09 (an
# out-of-scope resale-value question) was incorrectly treated as a confident
# match at 0.12 -- see docs/evaluation_report.md "Root Cause Analysis".
INDEX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                          "knowledge", "faiss_index")
EMBEDDER_STATE_PATH = os.path.join(INDEX_DIR, "embedder_state.pkl")

# --- Hybrid re-ranking fix (see docs/evaluation_report.md, "Failure Case 1")
# The offline TF-IDF+SVD embedding sometimes ranks a chunk that shares
# generic vocabulary ("check", "confirm") above the chunk that actually
# answers the question, because SVD compression blurs exact-term signal.
# We fix this by re-ranking the vector store's top-N candidates with a
# lexical keyword-overlap score and blending the two, which restores exact
# domain-term matches (e.g. "warranty", "engine") to the top position
# without discarding the semantic vector signal entirely.
STOPWORDS = {"is", "my", "the", "a", "an", "to", "of", "in", "for", "on",
             "and", "or", "hi", "car", "please", "can", "you", "i", "it",
             "still", "if", "do", "does", "am"}
RERANK_CANDIDATES = 8
LEXICAL_WEIGHT = 0.45


def _keyword_overlap(query: str, text: str) -> float:
    q_terms = {w.lower().strip(".,?!") for w in query.split()} - STOPWORDS
    if not q_terms:
        return 0.0
    t_lower = text.lower()
    hits = sum(1 for w in q_terms if w in t_lower)
    return hits / len(q_terms)


@dataclass
class RetrievedChunk:
    text: str
    source: str
    score: float


class Retriever:
    def __init__(self):
        self.store = VectorStore.load(INDEX_DIR)
        from retrieval.embedder import OfflineEmbedder
        if os.path.exists(EMBEDDER_STATE_PATH):
            self.embedder = OfflineEmbedder.load(EMBEDDER_STATE_PATH)
        else:
            self.embedder = get_embedder()

    def retrieve(self, query: str, k: int = 3) -> List[RetrievedChunk]:
        q_vec = self.embedder.embed_query(query)
        candidates = self.store.search(q_vec, k=max(k, RERANK_CANDIDATES))

        reranked = []
        for chunk, vec_score in candidates:
            lex_score = _keyword_overlap(query, chunk.text)
            blended = (1 - LEXICAL_WEIGHT) * vec_score + LEXICAL_WEIGHT * lex_score
            reranked.append((chunk, vec_score, lex_score, blended))
        reranked.sort(key=lambda t: -t[3])

        return [RetrievedChunk(text=c.text, source=c.source, score=blended)
                for c, vec_score, lex_score, blended in reranked[:k]]

    def retrieve_grounded(self, query: str, k: int = 3):
        """Returns (chunks, is_confident). is_confident False => agent must
        not answer from these chunks; it should escalate or ask a clarifying
        question instead of guessing."""
        chunks = self.retrieve(query, k=k)
        is_confident = bool(chunks) and chunks[0].score >= MIN_CONFIDENCE
        return chunks, is_confident
