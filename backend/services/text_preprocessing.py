import re
import fitz   # PyMuPDF

# ══════════════════════════════════════════════════════════════════
# TITLE EXTRACTION
# ══════════════════════════════════════════════════════════════════

def extract_title_from_pdf(pdf_bytes: bytes) -> str:
    """Title extraction from PDF using font size heuristics.
    Parameters:
    pdf_bytes (bytes): The PDF file as bytes.
    Returns:
    str: The extracted title or an empty string if not found.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return "PDF corrupted or unreadable"

    try:
        meta_title = doc.metadata.get("title", "").strip()
        if meta_title and len(meta_title) > 5:
            return meta_title[:512]

        if len(doc) == 0:
            return "PDF empty"

        page   = doc[0]
        blocks = page.get_text("dict")["blocks"]

        lines_data = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                line_text = ""
                max_size  = 0
                y0        = line["bbox"][1]
                for span in line.get("spans", []):
                    txt  = span.get("text", "").strip()
                    size = span.get("size", 0)
                    if txt:
                        line_text += txt + " "
                        max_size   = max(max_size, size)
                line_text = line_text.strip()
                if 8 < len(line_text) < 500:
                    lines_data.append({"text": line_text, "size": max_size, "y": y0})

        if not lines_data:
            return ""

        max_font    = max(l["size"] for l in lines_data)
        title_lines = [l for l in lines_data if abs(l["size"] - max_font) < 0.5]
        title_lines.sort(key=lambda x: x["y"])
        return " ".join(l["text"] for l in title_lines)[:512]

    finally:
        doc.close()

def extract_abstract_from_pdf(pdf_bytes: bytes) -> str:
    """Extracts the abstract from a PDF using keyword heuristics. It looks for common abstract keywords and extracts the text following them until it encounters stop keywords or reaches a reasonable length limit.
    Parameters:
    pdf_bytes (bytes): The PDF file as bytes.
    Returns:
    str: The extracted abstract or an empty string if not found.
    """

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return ""

    try:
        raw_text = ""

        # Scan the first few pages for abstract keywords
        for i in range(min(5, len(doc))):
            raw_text += doc[i].get_text("text") + "\n"

        raw_text = text_preprocessing(raw_text)

        # Normalize whitespace
        raw_text = re.sub(r"\n+", "\n", raw_text)
        raw_text = re.sub(r"[ \t]+", " ", raw_text)

        keywords_priority = [
            "özetçe",
            "özet",
            "abstract",
            "summary"
        ]

        stop_keywords = [
            "anahtar kelimeler",
            "keywords",
            "giriş",
            "introduction",
            "1.",
            "i.",
        ]

        lower_text = raw_text.lower()

        for keyword in keywords_priority:

            idx = lower_text.find(keyword)

            if idx == -1:
                continue

            # after keyword text
            section = raw_text[idx + len(keyword):]

            # Find the earliest occurrence of any stop keyword in the section
            end_positions = []

            for stop_word in stop_keywords:
                stop_idx = section.lower().find(stop_word)

                if stop_idx != -1:
                    end_positions.append(stop_idx)

            if end_positions:
                end_idx = min(end_positions)
                abstract = section[:end_idx]
            else:
                abstract = section[:2000]

            abstract = abstract.strip()

            # If the extracted abstract is too short, it is likely not valid, so we skip it and try the next keyword
            if len(abstract) < 100:
                continue

            return abstract

        return ""

    finally:
        doc.close()

# ══════════════════════════════════════════════════════════════════
# FULL TEXT EXTRACTION
# ══════════════════════════════════════════════════════════════════

def extract_full_text_from_pdf(pdf_bytes: bytes) -> str:
    """Full text extraction from PDF with basic cleaning.
    Parameters:
    pdf_bytes (bytes): The PDF file as bytes.
    Returns:
    str: The extracted full text.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return ""

    try:
        pages_text = []
        for page in doc:
            text = page.get_text()
            text = text_preprocessing(text)
            if text.strip():
                pages_text.append(text)
        full = "\n\n".join(pages_text)
        return text_preprocessing(full)
    finally:
        doc.close()

def text_preprocessing(text: str) -> str:
    """Basic text preprocessing to clean up the extracted text.
    Parameters:
    text (str): The raw extracted text.
    Returns:
    str: The preprocessed text.
    """

    # normalize newline
    text = re.sub(r'\r\n', '\n', text)
    # collapse excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # collapse spaces/tabs only
    text = re.sub(r'[ \t]+', ' ', text)
    # remove control chars EXCEPT newline/tab
    text = re.sub(r'[\x00-\x08\x0B-\x1F\x7F]', '', text)
    # remove repeated dots
    text = re.sub(r'\.{2,}', '.', text)

    return text.strip()

def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100
) -> list[str]:

    words = text.split()

    chunks = []

    step = chunk_size - overlap

    for i in range(0, len(words), step):

        chunk = words[i:i + chunk_size]

        if chunk:
            chunks.append(" ".join(chunk))

    return chunks