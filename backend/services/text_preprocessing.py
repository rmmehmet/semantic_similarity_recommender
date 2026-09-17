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
        return ""

    try:
        meta_title = doc.metadata.get("title", "").strip()
        if meta_title and len(meta_title) > 5:
            return meta_title[:512]

        if len(doc) == 0:
            return ""

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
# ABSTRACT EXTRACTION — section-marker tabanlı (tercih edilen yöntem)
# ══════════════════════════════════════════════════════════════════

# extract_abstract_from_pdf() saf bir anahtar-kelime arama (lower_text.find)
# kullanıyor — PDF'i ham metin olarak ikinci kez tarıyor, font/kalınlık
# bilgisini hiç görmüyor. Oysa extract_full_text_from_pdf() zaten "Özet"/
# "Abstract"/"Summary" başlığını _SECTION_KEYWORDS_RE ile font+numaralandırma
# sinyaliyle doğru tespit edip <<<SECTION:Özet>>> olarak işaretliyor — bu
# fonksiyon o işaretleyiciyi kullanarak abstract'ı çıkarır (daha güvenilir,
# çünkü "ÖZET" büyük harfle ya da beklenmedik bir sırada yazılmış olsa bile
# aynı başlık-tespit mekanizmasından geçmiş olur). Eşleşme bulunamazsa boş
# string döner — çağıran taraf extract_abstract_from_pdf()'e (keyword
# tabanlı, eski yöntem) fallback yapmalı.
_ABSTRACT_SECTION_KEYWORD_RE = re.compile(r"özet|abstract|summary", re.IGNORECASE)

# chunking_service.py'deki _MARKER_RE ile aynı kalıp — burada da işaretleyici
# ayrıştırmak için ayrıca tanımlanıyor (iki modül arasında private import
# yapılmıyor, kalıp basit ve stabil olduğu için kopyalamak daha temiz).
_MARKER_RE = re.compile(r"<<<(SECTION|SUBSECTION|PAGE):(.*?)>>>")


def extract_abstract_from_marked_text(marked_fulltext: str) -> str:
    """
    extract_full_text_from_pdf()'in döndürdüğü, <<<SECTION:..>>>/
    <<<SUBSECTION:..>>>/<<<PAGE:n>>> işaretleyicileri gömülü metinden Özet/
    Abstract/Summary bölümünün ham metnini çıkarır.

    Sadece Özet/Abstract/Summary ile eşleşen İLK <<<SECTION:..>>>'dan bir
    SONRAKİ <<<SECTION:..>>>'a kadar olan içerik toplanır — aradaki
    <<<SUBSECTION:..>>>/<<<PAGE:n>>> işaretleyicileri (nadiren olsa da bir
    özetin alt bölümü/sayfa geçişi olabilir) toplamayı KESMEZ, sadece yeni
    bir üst-seviye SECTION toplamayı durdurur.

    Eşleşme yoksa "" döner.
    """
    parts = _MARKER_RE.split(marked_fulltext)  # [önce, TİP, DEĞER, sonra, TİP, DEĞER, ...]

    collecting = False
    collected: list[str] = []
    i = 1
    while i + 1 < len(parts):
        mtype, mval = parts[i], parts[i + 1]
        segment = parts[i + 2] if i + 2 < len(parts) else ""

        if mtype == "SECTION":
            if collecting:
                break  # bir sonraki gerçek bölüme geçildi — abstract bitti
            if _ABSTRACT_SECTION_KEYWORD_RE.search(mval):
                collecting = True

        if collecting:
            collected.append(segment)
        i += 3

    result = " ".join(collected)
    result = re.sub(r"\s+", " ", result).strip()
    return result


# ══════════════════════════════════════════════════════════════════
# FULL TEXT EXTRACTION — bölüm/sayfa farkındalığı ile
# ══════════════════════════════════════════════════════════════════

# Numaralandırılmış ("1.1 Yöntem", "2. Giriş") ya da bilinen akademik bölüm
# adı (TR+EN) kalıbıyla başlayan satırlar — kalınlık/font boyutu kontrolü
# olmadan da güçlü bir başlık sinyalidir.
_SECTION_KEYWORDS_RE = re.compile(
    r"^(?:"
    r"\d+(?:\.\d+)*\.?\s+\S"                                   # "1.1 Yöntem", "2. Giriş"
    r"|(?:bölüm|chapter|section)\s*\d+"                        # "Bölüm 3", "Chapter 2"
    r"|(?:giriş|özet|abstract|introduction|summary"
    r"|yöntem|metodoloji|method(?:oloji|ology)?|materyal|material"
    r"|bulgular|results?|"
    r"tartışma|discussion|"
    r"sonuç|conclusion|"
    r"kaynak(?:ça)?|referanslar|references?|bibliography|"
    r"teşekkür|acknowledge?ments?|"
    r"ek(?:ler)?|appendix)\b"                                  # "Ek A", "Ekler", "Appendix B"
    r")",
    re.IGNORECASE,
)

# IEEE/mühendislik tarzı makalelerde çok yaygın: Roma rakamıyla numaralanmış
# bölümler ("I. INTRODUCTION", "II. METHODOLOGY") ve tek büyük harfle
# numaralanmış alt bölümler ("A. Dataset", "B. Model Architecture").
# Tek harf kalıbı ("A.", "B.") atıf/kısaltmalarla ("A. Yılmaz'ın çalışması")
# karışabileceğinden — arap rakamlı/anahtar-kelimeli kalıpların aksine —
# SALT regex'e güvenilmez; _heading_level() bunun için ayrıca kalın/büyük
# font şartı arar (bkz. aşağısı).
_ROMAN_HEADING_RE  = re.compile(r"^([IVXLCDM]{1,6})\.\s+\S")
_LETTER_HEADING_RE = re.compile(r"^([A-Z])\.\s+\S")
_VALID_ROMAN_RE    = re.compile(r"^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")

_HEADING_MAX_LEN = 140

# İçindekiler (Table of Contents) satırları genelde "1.1 Yöntem . . . 12"
# ya da "Kaynakça 29" gibi sonu nokta-dizisi/boşluk + sayfa numarasıyla biten
# bir formatta olur — numaralandırma/anahtar-kelime kalıbına uysa da bunlar
# GERÇEK başlık değildir (asıl başlık belgenin ilerisinde, sayfa numarası
# OLMADAN tekrar geçer). Sonu böyle bir "nokta-dizisi + sayı" ile biten
# satırları başlık adayı saymıyoruz.
_TOC_TRAILING_PAGE_RE = re.compile(r"[.\s]{2,}\d{1,4}$")

# Aşağıda gömülen <<<SECTION:..>>> / <<<SUBSECTION:..>>> / <<<PAGE:n>>>
# işaretleyicileri sadece yazdırılabilir ASCII kullanır — text_preprocessing()
# bunları bozmaz. chunking_service.py bunları ayrıştırıp chunk'lara
# section/subsection/page_start/page_end atar, sonra görünür metinden temizler.


def _is_bold(flags: int) -> bool:
    return bool(flags & (1 << 4))


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    return (s[mid - 1] + s[mid]) / 2 if n % 2 == 0 else s[mid]


def _heading_level(text: str, size: float, bold: bool, body_size: float) -> int:
    """0 = başlık değil, 1 = bölüm (section), 2 = alt bölüm (subsection)."""
    if not (2 <= len(text) <= _HEADING_MAX_LEN):
        return 0
    if _TOC_TRAILING_PAGE_RE.search(text):
        return 0  # İçindekiler satırı (sonda sayfa numarası) — gerçek başlık değil

    numbered = re.match(r"^(\d+(?:\.\d+)*)\.?\s+\S", text)
    if numbered:
        depth = numbered.group(1).count(".") + 1
        return 1 if depth == 1 else 2
    if _SECTION_KEYWORDS_RE.match(text):
        return 1

    # Roma rakamı ("I. INTRODUCTION") ve tek harf ("A. Dataset") kalıpları —
    # atıf/kısaltmalarla karışma riski nedeniyle SADECE kalın/büyük font
    # sinyaliyle BİRLİKTE kabul edilir, arap rakamı/anahtar-kelime gibi
    # tek başına regex'e güvenilmez.
    if bold or size >= body_size * 1.1:
        roman = _ROMAN_HEADING_RE.match(text)
        if roman and _VALID_ROMAN_RE.match(roman.group(1)):
            return 1  # "I.", "II.", "III." → bölüm
        if _LETTER_HEADING_RE.match(text):
            return 2  # "A.", "B.", "C." → alt bölüm (IEEE kuralı: harfler bölüm altına girer)

    if size >= body_size * 1.4:
        return 1
    if bold and size >= body_size * 1.1:
        return 2
    return 0


def extract_full_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    PDF'den tam metni çıkarır ve bölüm başlıklarını (font boyutu + kalınlık +
    numaralandırma/anahtar-kelime kalıpları — Türkçe ve İngilizce ikisi de)
    ve sayfa geçişlerini görünmez `<<<SECTION:..>>>` / `<<<SUBSECTION:..>>>` /
    `<<<PAGE:n>>>` işaretleyicileriyle metne gömer. chunking_service.py bu
    işaretleyicileri chunk'lara section/subsection/page_start/page_end olarak
    atar ve görünür metinden temizler — embedding/LLM ham işaretleyiciyi
    asla görmez.

    Parameters:
    pdf_bytes (bytes): The PDF file as bytes.
    Returns:
    str: The extracted full text, with inline section/page markers.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return ""

    try:
        # 1. geçiş — gövde metninin medyan font boyutunu bul (başlığı
        # "belirgin şekilde büyük" diye nitelemek için referans değer).
        sizes: list[float] = []
        for page in doc:
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            sizes.append(span.get("size", 0))
        body_size = _median(sizes) or 10.0

        pages_text: list[str] = []
        for page_idx, page in enumerate(doc, start=1):
            page_parts = [f"<<<PAGE:{page_idx}>>>"]
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                block_lines: list[str] = []
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    line_text = "".join(s.get("text", "") for s in spans).strip()
                    if not line_text:
                        continue
                    max_size = max((s.get("size", 0) for s in spans), default=0)
                    bold = any(_is_bold(s.get("flags", 0)) for s in spans)
                    level = _heading_level(line_text, max_size, bold, body_size)
                    if level == 1:
                        safe = line_text.replace(">>>", "").replace("<<<", "").strip()[:200]
                        block_lines.append(f"<<<SECTION:{safe}>>>")
                    elif level == 2:
                        safe = line_text.replace(">>>", "").replace("<<<", "").strip()[:200]
                        block_lines.append(f"<<<SUBSECTION:{safe}>>>")
                    block_lines.append(line_text)
                if block_lines:
                    page_parts.append("\n".join(block_lines))
            page_text = text_preprocessing("\n\n".join(page_parts))
            if page_text.strip():
                pages_text.append(page_text)

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