"""
Endpoint de exportação de documentos — converte texto ou HTML em arquivos para download direto.

Rotas:
  POST /api/agent/export-doc   → texto → DOCX ou PDF
  POST /api/agent/export-html  → HTML → PDF, PPTX, PNG ou JPEG
  POST /api/agent/export-design-source → design-source JSON → PDF, PPTX, PNG
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


def _is_playwright_browser_missing_error(exc: Exception) -> bool:
    message = str(exc)
    return (
        "Executable doesn't exist" in message
        or "playwright install" in message.lower()
        or "chrome-headless-shell" in message
    )


def _raise_export_dependency_error(exc: Exception) -> None:
    raise HTTPException(
        status_code=503,
        detail=(
            "Exportação indisponível no servidor: o browser do Playwright não está instalado. "
            "Execute `python -m playwright install --with-deps chromium` no ambiente do backend "
            "ou gere uma nova imagem com essa etapa incluída."
        ),
    ) from exc


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
    canvas_preset: Optional[str] = None  # "instagram-square" | "instagram-portrait" | "story" | "banner" | "widescreen"


class ExportDesignSourceRequest(BaseModel):
    source: dict[str, Any]
    title: str
    format: str  # "pdf" | "pptx" | "png"
    frame_index: Optional[int] = None


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
        if _is_playwright_browser_missing_error(e):
            _raise_export_dependency_error(e)
        logger.error(f"[EXPORT-DOC] Erro ao exportar '{fmt}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in title)[:50]
    filename = f"{safe_name}.{ext}"
    return Response(
        content=file_bytes,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export-design-source")
async def export_design_source(req: ExportDesignSourceRequest):
    """
    Converte design source (arcco.design-source/v1) em PNG/PDF/PPTX no backend.
    """
    fmt = req.format.lower()
    title = req.title or "design_source"

    try:
        if fmt == "png":
            from backend.services.design_source_export import render_design_source_png

            result = await render_design_source_png(
                req.source,
                frame_index=req.frame_index,
            )
            if isinstance(result, tuple):
                file_bytes, mime, ext = result
            else:
                file_bytes = result
                mime = "image/png"
                ext = "png"

        elif fmt == "pdf":
            from backend.services.design_source_export import render_design_source_pdf

            file_bytes = await render_design_source_pdf(
                req.source,
                frame_index=req.frame_index,
            )
            mime = "application/pdf"
            ext = "pdf"

        elif fmt == "pptx":
            from backend.services.design_source_export import render_design_source_pptx

            file_bytes = await render_design_source_pptx(
                req.source,
                title=title,
                frame_index=req.frame_index,
            )
            mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            ext = "pptx"

        else:
            raise HTTPException(status_code=400, detail=f"Formato inválido: {fmt}. Use 'png', 'pdf' ou 'pptx'.")

    except HTTPException:
        raise
    except Exception as e:
        if _is_playwright_browser_missing_error(e):
            _raise_export_dependency_error(e)
        logger.error(f"[EXPORT-DESIGN-SOURCE] Erro ao exportar '{fmt}': {e}")
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
    from backend.services.design_contract import normalize_design_html
    normalized_html = normalize_design_html(req.html, canvas_preset=req.canvas_preset)

    try:
        if fmt == "pdf":
            from backend.services.file_service import generate_pdf_playwright
            file_bytes = await generate_pdf_playwright(
                normalized_html,
                slide_index=req.slide_index,
                page_size=req.page_size,
                canvas_preset=req.canvas_preset,
            )
            mime = "application/pdf"
            ext = "pdf"

        elif fmt == "pptx":
            from backend.services.file_service import html_to_pptx
            file_bytes = await html_to_pptx(
                normalized_html, title,
                slide_index=req.slide_index,
                page_size=req.page_size,
                canvas_preset=req.canvas_preset,
            )
            mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            ext = "pptx"

        elif fmt in ("png", "jpeg", "jpg"):
            real_fmt = "jpeg" if fmt in ("jpeg", "jpg") else "png"
            from backend.services.file_service import html_to_screenshot
            result = await html_to_screenshot(
                normalized_html, real_fmt,
                slide_index=req.slide_index,
                resolution=req.resolution,
                canvas_preset=req.canvas_preset,
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
        if _is_playwright_browser_missing_error(e):
            _raise_export_dependency_error(e)
        logger.error(f"[EXPORT-HTML] Erro ao exportar '{fmt}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in title)[:50]
    filename = f"{safe_name}.{ext}"
    return Response(
        content=file_bytes,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
