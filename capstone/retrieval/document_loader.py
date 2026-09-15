"""
document_loader.py
Loads raw source documents (PDFs) from knowledge/raw/ and returns plain text
per document, tagged with source metadata. Uses pypdf for extraction.

In LangChain terms this plays the role of a DirectoryLoader + PyPDFLoader
pipeline (langchain_community.document_loaders). It is implemented directly
here (rather than importing langchain) so the ingestion pipeline runs in
network-restricted environments too -- see README "Offline Mode" section.
"""
import os
from dataclasses import dataclass
from typing import List

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None


@dataclass
class RawDocument:
    source: str          # filename, e.g. "company_policy.pdf"
    doc_id: str           # short id, e.g. "company_policy"
    text: str


def load_pdf(path: str) -> str:
    if PdfReader is None:
        raise RuntimeError("pypdf is required to load PDF knowledge sources.")
    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def load_knowledge_dir(raw_dir: str) -> List[RawDocument]:
    """Load every .pdf in raw_dir into a RawDocument list."""
    docs = []
    for fname in sorted(os.listdir(raw_dir)):
        if not fname.lower().endswith(".pdf"):
            continue
        full_path = os.path.join(raw_dir, fname)
        text = load_pdf(full_path)
        doc_id = os.path.splitext(fname)[0]
        docs.append(RawDocument(source=fname, doc_id=doc_id, text=text))
    return docs


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    raw_dir = os.path.join(here, "..", "knowledge", "raw")
    for d in load_knowledge_dir(raw_dir):
        print(f"--- {d.source} ({len(d.text)} chars) ---")
        print(d.text[:200].replace("\n", " "), "...")
