from __future__ import annotations
import re

# ══════════════════════════════════════════════════════════════════
# SENTENCE-AWARE CHUNKING  (for fulltext)
# ══════════════════════════════════════════════════════════════════

def chunk_fulltext(
    text: str,
    size: int    = 850,
    overlap: int = 100,
) -> list[str]:
    """It performs sentence-based chunking for fulltext. It tries to preserve sentence boundaries.
    Parameters:
    - text: The fulltext to be chunked.
    - size: The maximum character length of each chunk (default: 850).
    - overlap: The number of characters to overlap between consecutive chunks (default: 100).
    Returns:
    A list of text chunks, each ideally containing complete sentences and respecting the specified size and overlap.
    """
    text = text.strip()
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current            = ""

    for sent in sentences:
        # New candidate chunk if we add this sentence to the current chunk
        candidate = (current + " " + sent).strip() if current else sent

        if len(candidate) <= size:
            current = candidate
        else:
            # Save the current chunk if it's not empty
            if current:
                chunks.append(current)

            # Start a new chunk with the current sentence
            tail = current[-overlap:] if current and overlap > 0 else ""

            # Try to include the current sentence in the new chunk, but if it's too long, start fresh with just the sentence
            new_start = (tail + " " + sent).strip() if tail else sent

            if len(new_start) <= size:
                current = new_start
            else:
                # If the single sentence is too long, we have to split it directly (not ideal, but necessary)
                current = sent[:size]

    if current:
        chunks.append(current)

    return chunks

# ══════════════════════════════════════════════════════════════════
# ABSTRACT CHUNKING  (for abstract)
# ══════════════════════════════════════════════════════════════════

def chunk_abstract(abstract: str, max_len: int = 500) -> list[str]:
    """It performs a simple chunking for abstracts. It tries to preserve sentence boundaries but does not guarantee it.
    Parameters:
    - abstract: The abstract text to be chunked.
    - max_len: The maximum character length of the abstract chunk (default: 500).
    Returns:
    A list containing a single chunk of the abstract, ideally preserving sentence boundaries and respecting the specified maximum length. If the abstract is shorter than max_len, it returns the whole abstract as a single chunk.
    """
    abstract = abstract.strip()
    if not abstract:
        return []

    if len(abstract) <= max_len:
        return [abstract]

    # Try to cut at the last sentence boundary before max_len
    cut = abstract[:max_len]
    last_end = max(
        cut.rfind(". "),
        cut.rfind("! "),
        cut.rfind("? "),
    )
    if last_end > 100:
        cut = abstract[: last_end + 1].strip()

    return [cut]

# ══════════════════════════════════════════════════════════════════
# CHUNK RECORDS BUILDER
# ══════════════════════════════════════════════════════════════════

def build_chunk_records(
    title: str,
    abstract: str,
    fulltext: str,
) -> tuple[list[dict], list[str], list[str]]:
    """
    It builds chunk records for title, abstract, and fulltext. The title is kept as a single chunk, while the abstract and fulltext are chunked using their respective functions.
    Parameters:
    - title: The title of the document (not chunked).
    - abstract: The abstract of the document (chunked using chunk_abstract).
    - fulltext: The fulltext of the document (chunked using chunk_fulltext).
    Returns:
    A tuple containing:
    - records: A list of dictionaries representing the chunk records.
    - ft_chunks: A list of strings representing the fulltext chunks.
    - abs_chunks: A list of strings representing the abstract chunks.
    """
    records: list[dict] = []

    # ── Title ─────────────────────────────────
    if title:
        records.append(
            {"chunk_text": title, "chunk_idx": 0, "chunk_type": "title"}
        )

    # ── Abstract ──────────────────────────────────────────────
    abs_chunks = chunk_abstract(abstract)
    for i, ch in enumerate(abs_chunks):
        records.append(
            {"chunk_text": ch, "chunk_idx": i, "chunk_type": "abstract"}
        )

    # ── Fulltext ──────────────────────────────────────────────
    ft_chunks = chunk_fulltext(fulltext)
    for i, ch in enumerate(ft_chunks):
        records.append(
            {"chunk_text": ch, "chunk_idx": i, "chunk_type": "fulltext"}
        )

    return records, ft_chunks, abs_chunks