"""
Módulo de Tools do Arcco AI.

Este módulo contém o catálogo oficial de todas as tools disponíveis na plataforma.
Cada tool registrada aqui aparece automaticamente na tela "Loja de Tools" do frontend.

Para adicionar uma nova tool, consulte o arquivo README.md desta pasta.
"""

from .catalog import TOOLS_CATALOG, get_tool_by_id

__all__ = ["TOOLS_CATALOG", "get_tool_by_id"]
