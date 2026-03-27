"""
Endpoint de exportação de documentos — converte texto ou HTML em arquivos para download direto.

Rotas:
  POST /api/agent/export-doc   → texto → DOCX ou PDF
  POST /api/agent/export-html  → HTML → PDF, PPTX, PNG ou JPEG
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class ExportDocRequest(BaseModel):
    text: str
    title: str
    format: str  # "docx" | "pdf"


class ExportHtmlRequest(BaseModel):
    html: str
    title: str
    format: str  # "pdf" | "pptx" | "png" | "jpeg"
    slide_index: Optional[int] = None    # None = todos os slides, 0-based = slide específico
    page_size: Optional[str] = None      # "widescreen", "a4-landscape", "a4-portrait", "letter-landscape", "letter-portrait"
    resolution: Optional[str] = None     # "hd-720", "hd-1080"


@router.post("/export-doc")
async def export_doc(req: ExportDocRequest):
    """Converte texto/markdown em DOCX ou PDF para download direto (sem upload ao Supabase)."""
    fmt = req.format.lower()
    title = req.title or "documento"

    try:
        if fmt == "docx":
            from backend.services.file_service import generate_docx
            import asyncio
            file_bytes = await asyncio.to_thread(generate_docx, title, req.text)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ext = "docx"

        elif fmt == "pdf":
            try:
                from backend.services.file_service import _text_to_html, generate_pdf_playwright
                html = _text_to_html(title, req.text)
                file_bytes = await generate_pdf_playwright(html)
            except (ImportError, Exception) as pdf_exc:
                # Fallback: reportlab quando Playwright não está instalado
                logger.warning(f"[EXPORT-DOC] Playwright indisponível ({pdf_exc}), usando reportlab")
                import asyncio
                from backend.services.file_service import generate_pdf
                file_bytes = await asyncio.to_thread(generate_pdf, title, req.text)
            mime = "application/pdf"
            ext = "pdf"

        else:
            raise HTTPException(status_code=400, detail=f"Formato inválido: {fmt}. Use 'docx' ou 'pdf'.")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[EXPORT-DOC] Erro ao exportar '{fmt}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in title)[:50]
    filename = f"{safe_name}.{ext}"
    return Response(
        content=file_bytes,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export-html")
async def export_html(req: ExportHtmlRequest):
    """Converte HTML em PDF, PPTX, PNG ou JPEG para download direto."""
    fmt = req.format.lower()
    title = req.title or "apresentacao"

    try:
        if fmt == "pdf":
            from backend.services.file_service import generate_pdf_playwright
            file_bytes = await generate_pdf_playwright(
                req.html,
                slide_index=req.slide_index,
                page_size=req.page_size,
            )
            mime = "application/pdf"
            ext = "pdf"

        elif fmt == "pptx":
            from backend.services.file_service import html_to_pptx
            file_bytes = await html_to_pptx(
                req.html, title,
                slide_index=req.slide_index,
                page_size=req.page_size,
            )
            mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            ext = "pptx"

        elif fmt in ("png", "jpeg", "jpg"):
            real_fmt = "jpeg" if fmt in ("jpeg", "jpg") else "png"
            from backend.services.file_service import html_to_screenshot
            result = await html_to_screenshot(
                req.html, real_fmt,
                slide_index=req.slide_index,
                resolution=req.resolution,
            )
            # Se retorno é tuple, é ZIP multi-imagem (bytes, mime, ext)
            if isinstance(result, tuple):
                file_bytes, mime, ext = result
            else:
                file_bytes = result
                mime = f"image/{real_fmt}"
                ext = real_fmt

        else:
            raise HTTPException(status_code=400, detail=f"Formato inválido: {fmt}. Use 'pdf', 'pptx', 'png' ou 'jpeg'.")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[EXPORT-HTML] Erro ao exportar '{fmt}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in title)[:50]
    filename = f"{safe_name}.{ext}"
    return Response(
        content=file_bytes,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
