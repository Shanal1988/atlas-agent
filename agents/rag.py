"""
RAG module for Atlas.

Handles three document types:
  1. Annual reports  — PDF files dropped into data/reports/{TICKER}/
  2. Earnings calls  — TXT files dropped into data/transcripts/{TICKER}/
  3. Sector KB       — static markdown files in data/sector_kb/

Uses ChromaDB for persistent local vector storage and sentence-transformers
for embeddings. All functions degrade gracefully if either library is missing —
the pipeline continues with Tavily-only evidence, no crash.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# -- Optional dependency guards ------------------------------------------------

try:
    import chromadb  # noqa: F401
    _CHROMA_OK = True
except ImportError:
    _CHROMA_OK = False

try:
    from sentence_transformers import SentenceTransformer  # noqa: F401
    _ST_OK = True
except ImportError:
    _ST_OK = False

try:
    from pypdf import PdfReader  # noqa: F401
    _PYPDF_OK = True
except ImportError:
    _PYPDF_OK = False

_RAG_AVAILABLE = _CHROMA_OK and _ST_OK

# -- Paths ---------------------------------------------------------------------

_BASE          = Path(__file__).parent.parent
_VECTORSTORE   = _BASE / "data" / "vectorstore"
_REPORTS       = _BASE / "data" / "reports"
_TRANSCRIPTS   = _BASE / "data" / "transcripts"
_SECTOR_KB     = _BASE / "data" / "sector_kb"
_MANIFEST_PATH = _VECTORSTORE / "manifest.json"

# -- Chunking ------------------------------------------------------------------

_CHUNK_WORDS   = 300   # ~400 tokens
_OVERLAP_WORDS = 40    # ~50 tokens


def _chunk_text(text: str) -> list[str]:
    words  = text.split()
    step   = _CHUNK_WORDS - _OVERLAP_WORDS
    chunks = []
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + _CHUNK_WORDS]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


# -- Sector KB mapping ---------------------------------------------------------

def _map_sector(sector_industry: str) -> str | None:
    """Map a sector/industry string to a sector KB filename (without .md)."""
    text = sector_industry.lower()
    if any(kw in text for kw in ("payment", "money transfer", "remittance", "cross-border")):
        return "payments"
    if any(kw in text for kw in ("cyber", "security", "endpoint", "crowdstrike", "threat")):
        return "cybersecurity"
    if any(kw in text for kw in ("fintech", "financial technology", "financial services",
                                  "banking", "insurance", "credit", "capital market")):
        return "fintech"
    if any(kw in text for kw in ("saas", "cloud", "software", "infrastructure", "application")):
        return "cloud_saas"
    return None


# -- Singletons ----------------------------------------------------------------

_model  = None
_client = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _get_client():
    global _client
    if _client is None:
        _VECTORSTORE.mkdir(parents=True, exist_ok=True)
        import chromadb
        _client = chromadb.PersistentClient(path=str(_VECTORSTORE))
    return _client


def _collection_name(ticker: str) -> str:
    """Safe ChromaDB collection name for a ticker."""
    return "atlas_" + ticker.lower().replace(".", "_").replace("-", "_")


# -- Manifest ------------------------------------------------------------------

def _load_manifest() -> dict:
    if _MANIFEST_PATH.exists():
        with open(_MANIFEST_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_manifest(manifest: dict) -> None:
    _MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


# -- Embedding + upsert --------------------------------------------------------

def _upsert_chunks(collection_name: str, chunks: list[str],
                   metadatas: list[dict]) -> None:
    """Embed chunks and upsert into ChromaDB collection."""
    model  = _get_model()
    client = _get_client()

    embeddings = model.encode(chunks, show_progress_bar=False).tolist()
    collection = client.get_or_create_collection(
        collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    ids = [f"{collection_name}_{i}_{abs(hash(c)) % 10**8}" for i, c in enumerate(chunks)]
    collection.upsert(
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )


# -- Public indexing functions -------------------------------------------------

def index_pdf(ticker: str, pdf_path: str) -> int:
    """
    Chunk and embed a PDF annual report.
    Returns the number of chunks indexed, or 0 on failure.
    """
    if not _RAG_AVAILABLE or not _PYPDF_OK:
        return 0
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        pages  = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append((i + 1, text))

        full_text = "\n".join(t for _, t in pages)
        chunks    = _chunk_text(full_text)
        if not chunks:
            return 0

        fname = Path(pdf_path).name
        metas = [
            {"ticker": ticker, "source_type": "annual_report",
             "source_file": fname, "chunk_index": i}
            for i in range(len(chunks))
        ]
        _upsert_chunks(_collection_name(ticker), chunks, metas)
        return len(chunks)
    except Exception:
        return 0


def index_transcript(ticker: str, txt_path: str, label: str) -> int:
    """
    Chunk and embed an earnings call transcript (.txt).
    Returns the number of chunks indexed, or 0 on failure.
    """
    if not _RAG_AVAILABLE:
        return 0
    try:
        text   = Path(txt_path).read_text(encoding="utf-8", errors="ignore")
        chunks = _chunk_text(text)
        if not chunks:
            return 0

        fname = Path(txt_path).name
        metas = [
            {"ticker": ticker, "source_type": "transcript",
             "source_file": fname, "label": label, "chunk_index": i}
            for i in range(len(chunks))
        ]
        _upsert_chunks(_collection_name(ticker), chunks, metas)
        return len(chunks)
    except Exception:
        return 0


def index_sector_kb(sector: str) -> int:
    """
    Embed a sector KB markdown file from data/sector_kb/{sector}.md.
    Returns the number of chunks indexed, or 0 on failure.
    """
    if not _RAG_AVAILABLE:
        return 0
    try:
        kb_path = _SECTOR_KB / f"{sector}.md"
        if not kb_path.exists():
            return 0

        text   = kb_path.read_text(encoding="utf-8", errors="ignore")
        chunks = _chunk_text(text)
        if not chunks:
            return 0

        metas = [
            {"sector": sector, "source_type": "sector_kb",
             "source_file": f"{sector}.md", "chunk_index": i}
            for i in range(len(chunks))
        ]
        _upsert_chunks("atlas_sector_kb", chunks, metas)
        return len(chunks)
    except Exception:
        return 0


# -- Public query functions ----------------------------------------------------

def has_documents(ticker: str) -> bool:
    """True if any documents are indexed for this ticker."""
    if not _RAG_AVAILABLE:
        return False
    try:
        col = _get_client().get_collection(_collection_name(ticker))
        return col.count() > 0
    except Exception:
        return False


def retrieve(ticker: str, query: str, n: int = 4,
             include_sector: bool = True) -> str:
    """
    Query the vector store for ticker-specific documents + optional sector KB.
    Returns a formatted evidence string, or "" if no documents are indexed.
    """
    if not _RAG_AVAILABLE:
        return ""
    try:
        model  = _get_model()
        client = _get_client()
        qvec   = model.encode([query], show_progress_bar=False).tolist()

        sections = []

        # Ticker-specific documents
        try:
            col   = client.get_collection(_collection_name(ticker))
            count = col.count()
            if count > 0:
                res = col.query(query_embeddings=qvec, n_results=min(n, count))
                for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
                    src_type = meta.get("source_type", "document")
                    src_file = meta.get("source_file", "unknown")
                    sections.append(f"[{src_type}: {src_file}]\n{doc}")
        except Exception:
            pass

        # Sector KB
        if include_sector:
            try:
                kb_col = client.get_collection("atlas_sector_kb")
                kb_count = kb_col.count()
                if kb_count > 0:
                    kb_res = kb_col.query(
                        query_embeddings=qvec,
                        n_results=min(2, kb_count),
                    )
                    for doc, meta in zip(kb_res["documents"][0],
                                         kb_res["metadatas"][0]):
                        sector = meta.get("sector", "sector")
                        sections.append(f"[sector knowledge: {sector}]\n{doc}")
            except Exception:
                pass

        return "\n\n".join(sections) if sections else ""

    except Exception:
        return ""


# -- Auto-indexing (called from discovery.py) ----------------------------------

def auto_index(ticker: str, sector_industry: str = "") -> None:
    """
    Scan data/reports/{ticker}/ and data/transcripts/{ticker}/ for new files
    and index any not yet in the manifest. Also indexes the matching sector KB
    file if available. Silently skips if RAG libraries are not installed.
    """
    if not _RAG_AVAILABLE:
        return

    manifest = _load_manifest()
    changed  = False

    # -- PDF annual reports --
    reports_dir = _REPORTS / ticker
    if reports_dir.exists():
        for pdf_path in sorted(reports_dir.glob("*.pdf")):
            key = str(pdf_path)
            if key not in manifest:
                count = index_pdf(ticker, str(pdf_path))
                manifest[key] = {"type": "annual_report", "chunks": count}
                changed = True
                print(f"  [RAG] Indexed {pdf_path.name} -> {count} chunks")

    # -- Earnings transcripts --
    transcripts_dir = _TRANSCRIPTS / ticker
    if transcripts_dir.exists():
        for txt_path in sorted(transcripts_dir.glob("*.txt")):
            key = str(txt_path)
            if key not in manifest:
                label = txt_path.stem
                count = index_transcript(ticker, str(txt_path), label)
                manifest[key] = {"type": "transcript", "chunks": count}
                changed = True
                print(f"  [RAG] Indexed {txt_path.name} -> {count} chunks")

    # -- Sector KB --
    kb_sector = _map_sector(sector_industry)
    if kb_sector:
        kb_path = _SECTOR_KB / f"{kb_sector}.md"
        key     = str(kb_path)
        if key not in manifest and kb_path.exists():
            count = index_sector_kb(kb_sector)
            manifest[key] = {"type": "sector_kb", "chunks": count}
            changed = True
            print(f"  [RAG] Indexed sector KB: {kb_sector}.md -> {count} chunks")

    if changed:
        _save_manifest(manifest)
