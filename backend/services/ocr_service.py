"""
Serviço de OCR — extração de texto de imagens.
Portado de netlify/functions/ocr.ts (Tesseract)
"""

import logging
import tempfile

import httpx

logger = logging.getLogger(__name__)


async def ocr_image(image_url: str, lang: str = "por+eng") -> dict:
    """
    Faz OCR em uma imagem a partir de URL.

    Args:
        image_url: URL da imagem
        lang: Idioma(s) para OCR (default: português + inglês)

    Returns:
        {"text": str, "confidence": float}
    """
    try:
        import pytesseract
        from PIL import Image

        # Baixar imagem
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(image_url)
            response.raise_for_status()

        # Salvar temporariamente
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        # OCR
        image = Image.open(tmp_path)
        data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)

        # Extrair texto e calcular confiança
        texts = []
        confidences = []
        for i, text in enumerate(data["text"]):
            conf = int(data["conf"][i])
            if conf > 0 and text.strip():
                texts.append(text)
                confidences.append(conf)

        full_text = " ".join(texts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Cleanup
        import os
        os.unlink(tmp_path)

        logger.info(f"OCR completed: {len(full_text)} chars, confidence: {avg_confidence:.1f}%")

        return {
            "text": full_text,
            "confidence": round(avg_confidence, 2),
        }

    except ImportError:
        logger.error("pytesseract ou Pillow não instalado")
        raise ValueError("OCR não disponível: pytesseract não instalado")
    except Exception as e:
        logger.error(f"OCR error: {e}")
        raise
