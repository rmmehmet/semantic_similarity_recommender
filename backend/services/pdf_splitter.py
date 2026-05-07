import fitz
import re
import unicodedata

def safe_filename(name):
    """Convert a string to a safe filename by removing or replacing unsafe characters.
    Parameters:
    name (str): The original string to be converted into a safe filename.
    Returns:
    str: The converted safe filename."""
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"[^a-zA-Z0-9\s\-_]", "", name)
    name = re.sub(r"\s+", "-", name)

    return name.strip("-")

def fix_title(title):
    """Fix a title by removing or replacing unsafe characters.
    Parameters:
    title (str): The original title to be fixed.
    Returns:
    str: The fixed title."""
    title = re.sub(r'[\\/*?:"<>|]', "", title)
    return title.strip()

def split_pdf_by_font_size(file_bytes, font_threshold=22, original_filename=""):
    """Split a PDF into sections based on font size.
    Parameters:
    file_bytes (bytes): The PDF file as bytes.
    font_threshold (int): The font size threshold to determine section titles.
    original_filename (str): The original filename of the PDF file.
    Returns:
    dict: A dictionary containing the split sections and metadata."""

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")

        titles = []
        current_title_lines = []

        for page_num, page in enumerate(doc):
            blocks = page.get_text("dict")["blocks"]

            for b in blocks:

                if "lines" not in b:
                    continue

                for line in b["lines"]:

                    for span in line["spans"]:

                        font_size = span["size"]
                        text = span["text"].strip()

                        if not text:
                            continue

                        if font_size >= font_threshold:
                            current_title_lines.append(text)

                        elif current_title_lines:

                            full_title = " ".join(current_title_lines)

                            titles.append(
                                (page_num, full_title, full_title, font_threshold)
                            )

                            current_title_lines = []

            if current_title_lines:

                full_title = " ".join(current_title_lines)

                titles.append(
                    (page_num, full_title, full_title, font_threshold)
                )

                current_title_lines = []

        sections = []

        for i in range(len(titles)):

            start_page = titles[i][0]
            original_title = titles[i][1]
            clean_title = titles[i][2]
            font_size = titles[i][3]

            if i < len(titles) - 1:
                end_page = titles[i + 1][0]
            else:
                end_page = len(doc)

            pages = list(range(start_page, end_page))

            content = ""

            for page_num in pages:
                page = doc[page_num]
                content += page.get_text() + "\n"

            section = {
                "id": f"section_{i}",
                "title": original_title,
                "clean_title": clean_title,
                "start_page": start_page + 1,
                "end_page": end_page,
                "pages": [p + 1 for p in pages],
                "font_size": font_size,
                "content": content.strip(),
                "original_file": original_filename
            }

            sections.append(section)

        doc.close()

        return {
            "success": True,
            "sections": sections,
            "total_sections": len(sections),
            "original_file": original_filename,
            "font_threshold": font_threshold,
            "titles_found": len(titles)
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }