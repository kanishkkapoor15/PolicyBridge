"""ChromaDB vector store setup, knowledge base ingestion, and management."""

import logging
import re
from pathlib import Path

import chromadb

from config import CHROMA_PERSIST_DIR, KNOWLEDGE_BASE_DIR
from rag.embeddings import get_embedding_function

logger = logging.getLogger(__name__)

COLLECTION_NAME = "irish_eu_legal_corpus"

# Approximate tokens = words * 1.3; we use word count as proxy
MIN_CHUNK_WORDS = 60
MAX_CHUNK_WORDS = 500

_client: chromadb.ClientAPI | None = None


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    return _client


def get_collection():
    client = _get_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )


def _framework_name_from_file(filename: str) -> str:
    """Derive a human-readable framework name from the markdown filename."""
    name = filename.replace(".md", "").replace("_", " ").title()
    # Fix common acronyms
    for acronym in ("Gdpr", "Dpc", "Nis2", "Eu Ai", "Owta"):
        fixed = acronym.upper().replace(" ", " ")
        name = name.replace(acronym, fixed)
    name = name.replace("Eu Ai", "EU AI").replace("Nis2", "NIS2")
    return name


def _split_into_sections(text: str) -> list[dict]:
    """Split markdown text into sections by ## headings, with ### sub-splitting."""
    lines = text.split("\n")
    sections: list[dict] = []
    current_h2 = ""
    current_lines: list[str] = []

    def flush():
        if current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append({"heading": current_h2, "body": body})

    for line in lines:
        if line.startswith("## "):
            flush()
            current_h2 = line.lstrip("# ").strip()
            current_lines = []
        elif line.startswith("# ") and not line.startswith("## "):
            # Top-level title — use as context but don't create a section
            flush()
            current_h2 = current_h2 or line.lstrip("# ").strip()
            current_lines = []
        else:
            current_lines.append(line)

    flush()
    return sections


def _subsplit_large_section(heading: str, body: str) -> list[dict]:
    """If a section exceeds MAX_CHUNK_WORDS, split on ### subheadings."""
    word_count = len(body.split())
    if word_count <= MAX_CHUNK_WORDS:
        return [{"heading": heading, "body": body}]

    # Try splitting on ### headings
    parts = re.split(r"(?=^### )", body, flags=re.MULTILINE)
    chunks = []
    current_sub = heading
    current_text = ""

    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("### "):
            # Flush previous
            if current_text.strip():
                chunks.append({"heading": current_sub, "body": current_text.strip()})
            sub_heading_line = part.split("\n", 1)[0]
            current_sub = f"{heading} — {sub_heading_line.lstrip('# ').strip()}"
            current_text = part.split("\n", 1)[1] if "\n" in part else ""
        else:
            current_text += "\n" + part

    if current_text.strip():
        chunks.append({"heading": current_sub, "body": current_text.strip()})

    # Merge tiny chunks with the next one
    merged = []
    for chunk in chunks:
        if merged and len(merged[-1]["body"].split()) < MIN_CHUNK_WORDS:
            merged[-1]["body"] += "\n\n" + chunk["body"]
            merged[-1]["heading"] = merged[-1]["heading"].split(" — ")[0] + " — " + chunk["heading"].split(" — ")[-1] if " — " in chunk["heading"] else merged[-1]["heading"]
        else:
            merged.append(chunk)

    # If last chunk is too small, merge with previous
    if len(merged) > 1 and len(merged[-1]["body"].split()) < MIN_CHUNK_WORDS:
        merged[-2]["body"] += "\n\n" + merged[-1]["body"]
        merged.pop()

    return merged if merged else [{"heading": heading, "body": body}]


def _chunk_document(filepath: Path) -> list[dict]:
    """Read a markdown file and return a list of chunks with metadata."""
    text = filepath.read_text(encoding="utf-8")
    framework_name = _framework_name_from_file(filepath.name)
    sections = _split_into_sections(text)

    chunks = []
    for section in sections:
        sub_chunks = _subsplit_large_section(section["heading"], section["body"])
        for sc in sub_chunks:
            # Prefix chunk text with context header for better retrieval
            prefixed_text = f"[{framework_name} — {sc['heading']}] {sc['body']}"
            chunks.append({
                "text": prefixed_text,
                "metadata": {
                    "source_file": filepath.name,
                    "framework_name": framework_name,
                    "section_title": sc["heading"],
                },
            })

    return chunks


def is_knowledge_base_ingested() -> bool:
    """Check if the collection already has documents."""
    try:
        collection = get_collection()
        return collection.count() > 0
    except Exception:
        return False


def get_collection_stats() -> dict:
    """Return chunk counts per framework."""
    collection = get_collection()
    total = collection.count()
    if total == 0:
        return {"total": 0, "frameworks": {}}

    # Get all metadata to count per framework
    results = collection.get(include=["metadatas"])
    framework_counts: dict[str, int] = {}
    for meta in results["metadatas"]:
        fw = meta.get("framework_name", "unknown")
        framework_counts[fw] = framework_counts.get(fw, 0) + 1

    return {"total": total, "frameworks": framework_counts}


def ingest_knowledge_base(knowledge_base_dir: str | None = None):
    """Read all .md files from the knowledge base, chunk, embed, and store."""
    kb_dir = Path(knowledge_base_dir) if knowledge_base_dir else KNOWLEDGE_BASE_DIR
    md_files = sorted(kb_dir.glob("*.md"))

    if not md_files:
        logger.warning(f"No .md files found in {kb_dir}")
        return

    collection = get_collection()

    all_ids = []
    all_texts = []
    all_metadatas = []

    for filepath in md_files:
        chunks = _chunk_document(filepath)
        logger.info(f"  {filepath.name}: {len(chunks)} chunks")

        for i, chunk in enumerate(chunks):
            doc_id = f"{filepath.stem}__chunk_{i}"
            all_ids.append(doc_id)
            all_texts.append(chunk["text"])
            all_metadatas.append({**chunk["metadata"], "chunk_index": i})

    # Batch upsert
    batch_size = 100
    for start in range(0, len(all_ids), batch_size):
        end = start + batch_size
        collection.upsert(
            ids=all_ids[start:end],
            documents=all_texts[start:end],
            metadatas=all_metadatas[start:end],
        )

    logger.info(f"Ingested {len(all_ids)} chunks from {len(md_files)} files")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Allow running from backend/ directory
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    logger.info("Ingesting knowledge base...")
    ingest_knowledge_base()
    stats = get_collection_stats()
    logger.info(f"\nTotal chunks: {stats['total']}")
    logger.info("Per framework:")
    for fw, count in sorted(stats["frameworks"].items()):
        logger.info(f"  {fw}: {count}")
