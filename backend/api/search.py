"""
Endpoint de busca web.
Portado de netlify/functions/search.ts
"""

from fastapi import APIRouter, HTTPException

from backend.models.schemas import SearchRequest
from backend.services.search_service import search_web

router = APIRouter()


@router.post("/search")
async def search_endpoint(req: SearchRequest):
    """Busca na web via Tavily/Brave."""
    try:
        result = await search_web(
            query=req.query,
            max_results=req.max_results or 5,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
