"""
API de Tools — expõe o catálogo para o frontend.

Endpoints:
  GET /api/agent/tools           → lista todas as tools do catálogo
  GET /api/agent/tools/{tool_id} → retorna uma tool específica
"""

from fastapi import APIRouter, HTTPException
from backend.tools.catalog import TOOLS_CATALOG, get_tool_by_id

router = APIRouter()


@router.get("/tools")
async def list_tools():
    """Retorna o catálogo completo de tools."""
    return TOOLS_CATALOG


@router.get("/tools/{tool_id}")
async def get_tool(tool_id: str):
    """Retorna uma tool específica pelo ID."""
    tool = get_tool_by_id(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' não encontrada.")
    return tool
