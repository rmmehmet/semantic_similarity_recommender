import logging

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from services.pdf_splitter import split_pdf_by_font_size
from services.upload_validation import read_and_validate_pdf
import fitz
import io

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/split")
async def split_pdf(
    file: UploadFile = File(...),
    font_threshold: float = Form(22.0)
):
    """Split a PDF into sections based on font size."""
    file_bytes = await read_and_validate_pdf(file)
    result = split_pdf_by_font_size(
        file_bytes=file_bytes,
        font_threshold=font_threshold,
        original_filename=file.filename
    )
    return result

@router.post("/download-section")
async def download_section(
    file: UploadFile = File(...),
    start_page: int = Form(...),
    end_page: int = Form(...),
    title: str = Form("bolum")
):
    """Download the page range from the original PDF as a PDF file."""
    file_bytes = await read_and_validate_pdf(file)
    try:
        pdf_bytes = _extract_pages(file_bytes, start_page, end_page)
        safe_title = _safe_filename(title)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_title}.pdf"',
                "Content-Length": str(len(pdf_bytes))
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("[PDF] download-section hatası: %s", e)
        raise HTTPException(status_code=500, detail="PDF işlenirken bir hata oluştu.")

@router.post("/preview-section")
async def preview_section(
    file: UploadFile = File(...),
    start_page: int = Form(...),
    end_page: int = Form(...),
):
    """Returns the page range inline for PDF preview."""
    file_bytes = await read_and_validate_pdf(file)
    try:
        pdf_bytes = _extract_pages(file_bytes, start_page, end_page)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": "inline",
                "Content-Length": str(len(pdf_bytes))
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("[PDF] preview-section hatası: %s", e)
        raise HTTPException(status_code=500, detail="PDF işlenirken bir hata oluştu.")

# ── Auxiliary Functions ────────────────────────────────────────────────────
def _extract_pages(file_bytes: bytes, start_page: int, end_page: int) -> bytes:
    """Extract a page range from a PDF file and return it as bytes.
    Parameters:
    file_bytes (bytes): The PDF file as bytes.
    start_page (int): The starting page number.
    end_page (int): The ending page number.
    Returns:
    bytes: The extracted pages as a PDF file."""

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        s = max(0, start_page - 1)
        e = min(len(doc), end_page) - 1
        if s > e or s >= len(doc):
            raise ValueError(
                f"Geçersiz sayfa aralığı: start_page={start_page}, end_page={end_page}, "
                f"toplam sayfa={len(doc)}"
            )
        writer = fitz.open()
        try:
            writer.insert_pdf(doc, from_page=s, to_page=e)
            return writer.tobytes()
        finally:
            writer.close()
    finally:
        doc.close()

def _safe_filename(name: str) -> str:
    """Convert a string to a safe filename by removing or replacing unsafe characters.
    Parameters:
    name (str): The original string to be converted into a safe filename.
    Returns:
    str: The safe filename."""

    import re, unicodedata
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", "-", name)
    return name[:100].strip("-") or "bolum"