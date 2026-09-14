from fastapi import APIRouter, Depends, UploadFile, File, Form
from services.comparison_service import run_compare
from services.highlight_service  import run_compare_highlight
from services.rate_limit import rate_limit

router = APIRouter()

@router.post("/compare", dependencies=[Depends(rate_limit)])
async def compare_documents(
    target_file:   UploadFile       = File(...),
    compare_files: list[UploadFile] = File(...),
    search_type:   str              = Form("fulltext"),
):
    """Compare the target PDF with one or more PDFs and return similarity results."""
    return await run_compare(target_file, compare_files, search_type)

@router.post("/compare-highlight", dependencies=[Depends(rate_limit)])
async def compare_highlight(
    target_file:  UploadFile = File(...),
    compare_file: UploadFile = File(...),
    search_type:  str        = Form("fulltext"),
    top_words:    int        = Form(60),
):
    """Compare two PDFs and return highlighted similarities."""
    return await run_compare_highlight(target_file, compare_file, search_type, top_words)