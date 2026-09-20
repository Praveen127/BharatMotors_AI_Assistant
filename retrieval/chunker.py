"""
chunker.py
Splits loaded documents into overlapping text chunks for embedding, mirroring
LangChain's RecursiveCharacterTextSplitter behaviour (split on paragraph, then
sentence, then character boundaries; fixed chunk size with overlap).
"""
import re
import uuid
from dataclasses import dataclass, asdict
from typing import List
from retrieval.document_loader import RawDocument

CHUNK_SIZE = 500       # characters
CHUNK_OVERLAP = 80     # characters


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    source: str
    text: str
    position: int


def _split_paragraphs(text: str) -> List[str]:
    paras = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paras if p.strip()]


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Recursive-ish splitter: paragraph-aware, falls back to fixed windows."""
    chunks = []
    buffer = ""
    for para in _split_paragraphs(text):
        if len(buffer) + len(para) + 1 <= chunk_size:
            buffer = f"{buffer}\n{para}".strip()
        else:
            if buffer:
                chunks.append(buffer)
            if len(para) <= chunk_size:
                buffer = para
            else:
                # paragraph itself too long -> fixed-window split with overlap
                start = 0
                while start < len(para):
                    end = start + chunk_size
                    chunks.append(para[start:end])
                    start = end - overlap
                buffer = ""
    if buffer:
        chunks.append(buffer)
    return chunks


def chunk_documents(docs: List[RawDocument]) -> List[Chunk]:
    all_chunks: List[Chunk] = []
    for doc in docs:
        pieces = chunk_text(doc.text)
        for i, piece in enumerate(pieces):
            all_chunks.append(Chunk(
                chunk_id=f"{doc.doc_id}_{i:03d}_{uuid.uuid4().hex[:6]}",
                doc_id=doc.doc_id,
                source=doc.source,
                text=piece,
                position=i,
            ))
    return all_chunks


def chunks_to_json(chunks: List[Chunk]) -> List[dict]:
    return [asdict(c) for c in chunks]
