from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from services.pdf_splitter import split_pdf_by_font_size
import fitz
import io

router = APIRouter()

@router.post("/split")
async def split_pdf(
    file: UploadFile = File(...),
    font_threshold: float = Form(22.0)
):
    file_bytes = await file.read()
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
    """Orijinal PDF'den sayfa aralığını PDF olarak indir (attachment)."""
    file_bytes = await file.read()
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview-section")
async def preview_section(
    file: UploadFile = File(...),
    start_page: int = Form(...),
    end_page: int = Form(...),
):
    """Sayfa aralığını PDF olarak inline döndür (önizleme için)."""
    file_bytes = await file.read()
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Yardımcılar ────────────────────────────────────────────────────
def _extract_pages(file_bytes: bytes, start_page: int, end_page: int) -> bytes:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    writer = fitz.open()
    s = max(0, start_page - 1)        # 1-tabanlı → 0-tabanlı
    e = min(len(doc), end_page) - 1   # end_page dahil
    writer.insert_pdf(doc, from_page=s, to_page=e)
    pdf_bytes = writer.tobytes()
    writer.close()
    doc.close()
    return pdf_bytes


def _safe_filename(name: str) -> str:
    import re, unicodedata
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", "-", name)
    return name[:100].strip("-") or "bolum"