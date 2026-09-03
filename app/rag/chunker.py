"""
RAG Step 1: Chunker
Splits FOMC documents into semantically coherent chunks per the Implementation Plan (Section 9).

Chunking strategy:
- Statements: single chunk (they're ~500 words, short enough to be one unit)
- Minutes: split on known section headers (Fed uses consistent headers for 20+ years)
- Fallback: sliding window with 50-word overlap for any other doc type

Metadata per chunk: meeting_date, doc_type, chunk_index, word_count, source_url
"""
import re
import uuid
from typing import List, Dict, Any

from app.core.logger import setup_logger

logger = setup_logger(__name__)

# Known FOMC minutes section headers — deterministic, not LLM-based
MINUTES_SECTION_HEADERS = [
    "Staff Review of the Economic Situation",
    "Staff Review of the Financial Situation",
    "Staff Economic Outlook",
    "Participants' Views on Current Conditions and the Economic Outlook",
    "Committee Policy Action",
    "Review of Monetary Policy Strategy, Tools, and Communication",
    "Developments in Financial Markets and Open Market Operations",
]

def chunk_document(
    document_id: str,
    meeting_id: str,
    doc_type: str,
    raw_text: str,
    meeting_date: str,
    source_url: str,
) -> List[Dict[str, Any]]:
    """
    Returns a list of chunk dicts ready to insert into document_chunks table.
    Each chunk has: document_id, meeting_id, chunk_index, text, doc_type,
                    meeting_date, word_count, source_url
    """
    logger.info(f"Chunking {doc_type} document from {meeting_date} ({len(raw_text.split())} words)")

    if doc_type == "statement":
        # Statements are short (~500 words) — treat as a single chunk
        chunks = [raw_text.strip()]
    elif doc_type == "minutes":
        chunks = _split_on_headers(raw_text, MINUTES_SECTION_HEADERS)
    else:
        # Fallback: sliding window, 400 words per chunk, 50-word overlap
        chunks = _sliding_window(raw_text, window=400, overlap=50)

    result = []
    for i, chunk_text in enumerate(chunks):
        chunk_text = chunk_text.strip()
        if len(chunk_text.split()) < 20:
            # Skip tiny fragments
            continue
        result.append({
            "id": str(uuid.uuid4()),
            "document_id": document_id,
            "meeting_id": meeting_id,
            "chunk_index": i,
            "text": chunk_text,
            "doc_type": doc_type,
            "meeting_date": meeting_date,
            "word_count": len(chunk_text.split()),
            "source_url": source_url,
        })

    logger.info(f"Produced {len(result)} chunks from {doc_type} document")
    return result


def _split_on_headers(text: str, headers: List[str]) -> List[str]:
    """Split text on known section headers. Falls back to whole text if no headers found."""
    pattern = "|".join(re.escape(h) for h in headers)
    parts = re.split(f"({pattern})", text, flags=re.IGNORECASE)

    # Re-attach each header to the section that follows it
    sections = []
    i = 0
    while i < len(parts):
        if i + 1 < len(parts) and any(
            parts[i].strip().lower().startswith(h.lower()[:15]) for h in headers
        ):
            # This is a header — attach it to the next part
            sections.append(parts[i] + parts[i + 1] if i + 1 < len(parts) else parts[i])
            i += 2
        else:
            if parts[i].strip():
                sections.append(parts[i])
            i += 1

    if len(sections) <= 1:
        # No headers found — fall back to sliding window
        logger.warning("No section headers found in minutes — using sliding window fallback")
        return _sliding_window(text, window=400, overlap=50)

    return sections


def _sliding_window(text: str, window: int = 400, overlap: int = 50) -> List[str]:
    """Fallback chunker: fixed-size sliding window over words."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + window, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += window - overlap
    return chunks
