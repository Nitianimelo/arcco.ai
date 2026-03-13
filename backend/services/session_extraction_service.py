"""
Extração assíncrona de texto para arquivos efêmeros de sessão.

Estratégia:
- PDF: tenta PyMuPDF primeiro
- Se o PDF não tiver texto útil, cai para OCR por página
- DOCX/XLSX/TXT/CSV/MD: leitura nativa
- Imagens: OCR direto
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from backend.services.session_file_service import (
    get_extracted_file_path,
    get_stored_file_path,
    mark_file_failed,
    mark_file_processing,
    mark_file_ready,
)

logger = logging.getLogger(__name__)

PDF_NATIVE_MIN_CHARS = 80


def process_uploaded_file(session_id: str, file_id: str) -> None:
    try:
        entry = mark_file_processing(session_id, file_id)
        file_path = get_stored_file_path(session_id, file_id)
        extracted_text = extract_text_for_file(file_path, entry.get("mime_type", ""))
        output_path = get_extracted_file_path(session_id, file_id)
        write_extracted_text(output_path, extracted_text)
        mark_file_ready(session_id, file_id)
        logger.info(
            "Extração concluída para arquivo %s da sessão %s (%s chars)",
            file_id,
            session_id,
            len(extracted_text),
        )
    except Exception as exc:
        logger.error(
            "Falha na extração do arquivo %s da sessão %s: %s",
            file_id,
            session_id,
            exc,
        )
        mark_file_failed(session_id, file_id, str(exc))


def extract_text_for_file(file_path: Path, mime_type: str = "") -> str:
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        native_text = extract_pdf_text_native(file_path)
        if len(native_text.strip()) >= PDF_NATIVE_MIN_CHARS:
            return native_text
        logger.info(
            "PDF %s sem texto suficiente via PyMuPDF (%s chars). Acionando OCR.",
            file_path.name,
            len(native_text.strip()),
        )
        return extract_pdf_text_with_ocr(file_path)

    if suffix == ".docx":
        return extract_docx_text(file_path)

    if suffix == ".xlsx":
        return extract_xlsx_text(file_path)

    if suffix in {".txt", ".md", ".csv"}:
        return extract_plain_text(file_path)

    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"} or mime_type.startswith("image/"):
        return extract_image_text_with_ocr(file_path)

    return extract_plain_text(file_path)


def extract_pdf_text_native(file_path: Path) -> str:
    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF não instalado. Usando fallback PyPDF2 para %s", file_path.name)
        return extract_pdf_text_pypdf2(file_path)

    texts: list[str] = []
    try:
        with fitz.open(file_path) as document:
            for page in document:
                page_text = page.get_text("text") or ""
                if page_text.strip():
                    texts.append(page_text.strip())
        return "\n\n".join(texts).strip()
    except Exception as exc:
        logger.error("Erro na leitura nativa do PDF %s: %s", file_path, exc)
        raise


def extract_pdf_text_pypdf2(file_path: Path) -> str:
    try:
        import PyPDF2
    except ImportError as exc:
        raise ValueError("PyPDF2 não instalado. Não foi possível extrair texto do PDF.") from exc

    try:
        texts: list[str] = []
        with file_path.open("rb") as file_obj:
            reader = PyPDF2.PdfReader(file_obj)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    texts.append(page_text.strip())
        return "\n\n".join(texts).strip()
    except Exception as exc:
        logger.error("Erro no fallback PyPDF2 para %s: %s", file_path, exc)
        raise


def extract_pdf_text_with_ocr(file_path: Path) -> str:
    try:
        import fitz
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise ValueError(
            "Dependências de OCR para PDF não estão instaladas. "
            "Instale PyMuPDF para renderizar páginas e use OCR em PDFs escaneados."
        ) from exc

    page_texts: list[str] = []
    try:
        with fitz.open(file_path) as document:
            for index, page in enumerate(document):
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = Image.open(io.BytesIO(pix.tobytes("png")))
                text = pytesseract.image_to_string(image, lang="por+eng")
                if text.strip():
                    page_texts.append(f"[Página {index + 1}]\n{text.strip()}")
        return "\n\n".join(page_texts).strip()
    except Exception as exc:
        logger.error("Erro no OCR do PDF %s: %s", file_path, exc)
        raise


def extract_docx_text(file_path: Path) -> str:
    try:
        import docx
    except ImportError as exc:
        raise ValueError("python-docx não instalado.") from exc

    try:
        document = docx.Document(file_path)
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        return "\n".join(paragraphs).strip()
    except Exception as exc:
        logger.error("Erro ao extrair DOCX %s: %s", file_path, exc)
        raise


def extract_xlsx_text(file_path: Path) -> str:
    try:
        import openpyxl
    except ImportError as exc:
        raise ValueError("openpyxl não instalado.") from exc

    try:
        workbook = openpyxl.load_workbook(file_path, data_only=True)
        lines: list[str] = []
        for sheet in workbook.worksheets:
            lines.append(f"--- Planilha: {sheet.title} ---")
            for row in sheet.iter_rows(values_only=True):
                values = [str(value) if value is not None else "" for value in row]
                if any(values):
                    lines.append("\t".join(values))
        return "\n".join(lines).strip()
    except Exception as exc:
        logger.error("Erro ao extrair XLSX %s: %s", file_path, exc)
        raise


def extract_plain_text(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception as exc:
        logger.error("Erro ao ler arquivo texto %s: %s", file_path, exc)
        raise


def extract_image_text_with_ocr(file_path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise ValueError("Dependências de OCR de imagem não estão instaladas.") from exc

    try:
        image = Image.open(file_path)
        return pytesseract.image_to_string(image, lang="por+eng").strip()
    except Exception as exc:
        logger.error("Erro no OCR da imagem %s: %s", file_path, exc)
        raise


def write_extracted_text(output_path: Path, text: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        output_path.write_text(text or "", encoding="utf-8")
    except Exception as exc:
        logger.error("Falha ao salvar texto extraído em %s: %s", output_path, exc)
        raise
