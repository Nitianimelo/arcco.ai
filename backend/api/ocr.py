"""
Endpoint de OCR.
Portado de netlify/functions/ocr.ts
"""

from fastapi import APIRouter, HTTPException

from backend.models.schemas import OCRRequest, OCRResponse
from backend.services.ocr_service import ocr_image

router = APIRouter()


@router.post("/ocr", response_model=OCRResponse)
async def ocr_endpoint(req: OCRRequest):
    """OCR de imagem a partir de URL."""
    if not req.image_url:
        raise HTTPException(status_code=400, detail="Missing image_url")

    try:
        result = await ocr_image(req.image_url)
        return OCRResponse(text=result["text"], confidence=result["confidence"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
