"""
Skill: Local Lead Extractor (SDR)

A partir de um nicho e localizacao, busca empresas e compila dados
de contato (Nome, Site, Telefone, Redes Sociais) em formato tabular.

Usa o sandbox E2B para rodar scripts Python de scraping com APIs
publicas (DuckDuckGo Search, requests) de forma isolada e segura.

O resultado e uma tabela Markdown + instrucao para gerar CSV.
"""

import json
import logging
import os
import textwrap

from backend.core.llm import call_openrouter
from backend.agents import registry

logger = logging.getLogger(__name__)

# ── Contrato da Skill ─────────────────────────────────────────────────────────

SKILL_META = {
    "id": "local_lead_extractor",
    "name": "Extrator de Leads Locais",
    "description": (
        "Busca empresas/leads a partir de um nicho e localizacao. "
        "Retorna uma lista com Nome, Site, Telefone e Redes Sociais. "
        "Pode buscar no Google Maps, Instagram ou web geral. "
        "Use quando o usuario pedir leads, prospectar clientes, buscar empresas "
        "de um segmento ou montar lista de prospecao."
    ),
    "keywords": [
        "lead", "leads", "prospectar", "prospecao", "prospeccao",
        "buscar empresas", "lista de clientes", "scraping", "extrator",
        "google maps", "instagram", "concorrentes", "nicho",
        "b2b", "sdr", "vendas", "contatos",
    ],
    "parameters": {
        "type": "object",
        "properties": {
            "niche": {
                "type": "string",
                "description": "Nicho ou tipo de empresa a buscar. Ex: 'dentistas', 'clinicas de estetica', 'restaurantes japoneses'",
            },
            "location": {
                "type": "string",
                "description": "Cidade ou regiao. Ex: 'Sao Paulo', 'Rio de Janeiro, Zona Sul'",
            },
            "platform": {
                "type": "string",
                "description": "Plataforma de busca: 'google_maps', 'instagram' ou 'web' (padrao: 'web')",
                "enum": ["google_maps", "instagram", "web"],
            },
            "max_results": {
                "type": "integer",
                "description": "Numero maximo de leads a buscar (padrao: 20, max: 50)",
            },
        },
        "required": ["niche", "location"],
    },
}


# ── Script templates para E2B ──────────────────────────────────────────────────

def _build_search_script(niche: str, location: str, platform: str, max_results: int) -> str:
    """Gera o script Python a ser executado no sandbox E2B."""

    if platform == "instagram":
        search_query = f"{niche} {location} instagram"
    elif platform == "google_maps":
        search_query = f"{niche} em {location} telefone site"
    else:
        search_query = f"{niche} {location} telefone contato site"

    return textwrap.dedent(f"""\
import json
import re
import subprocess
import sys

# Instala dependencias no sandbox
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "duckduckgo-search"])

from duckduckgo_search import DDGS

query = {json.dumps(search_query, ensure_ascii=False)}
max_results = {max_results}
platform = {json.dumps(platform)}

leads = []
seen_names = set()

try:
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results * 3, region="br-pt"))

    for r in results:
        if len(leads) >= max_results:
            break

        title = r.get("title", "").strip()
        body = r.get("body", "")
        href = r.get("href", "")

        # Pula resultados genericos
        if not title or title.lower() in seen_names:
            continue
        if any(skip in href.lower() for skip in ["wikipedia", "youtube.com/watch", "facebook.com/login"]):
            continue

        seen_names.add(title.lower())

        # Extrai telefone do body
        phone_match = re.search(r"\\(?\\d{{2}}\\)?\\s*\\d{{4,5}}-?\\d{{4}}", body)
        phone = phone_match.group() if phone_match else ""

        # Extrai Instagram do body ou href
        insta_match = re.search(r"@([\\w.]+)", body)
        instagram = f"@{{insta_match.group(1)}}" if insta_match else ""
        if not instagram and "instagram.com/" in href:
            insta_path = href.split("instagram.com/")[-1].split("/")[0].split("?")[0]
            if insta_path:
                instagram = f"@{{insta_path}}"

        leads.append({{
            "nome": title,
            "site": href if not "instagram.com" in href else "",
            "telefone": phone,
            "instagram": instagram,
            "fonte": href,
        }})

except Exception as e:
    print(f"ERRO_BUSCA: {{e}}")

# Output como JSON
print("LEADS_JSON_START")
print(json.dumps(leads, ensure_ascii=False, indent=2))
print("LEADS_JSON_END")
print(f"Total: {{len(leads)}} leads encontrados")
""")


def _parse_leads_from_output(output: str) -> list[dict]:
    """Extrai a lista de leads do output do sandbox."""
    import re
    match = re.search(r"LEADS_JSON_START\s*([\s\S]*?)\s*LEADS_JSON_END", output)
    if match:
        return json.loads(match.group(1))
    return []


def _leads_to_markdown_table(leads: list[dict]) -> str:
    """Converte lista de leads em tabela Markdown."""
    if not leads:
        return "Nenhum lead encontrado."

    lines = ["| # | Nome | Site | Telefone | Instagram |", "|---|------|------|----------|-----------|"]
    for i, lead in enumerate(leads, 1):
        nome = lead.get("nome", "").replace("|", "/")[:60]
        site = lead.get("site", "")
        if site:
            site = f"[Link]({site})"
        telefone = lead.get("telefone", "")
        instagram = lead.get("instagram", "")
        lines.append(f"| {i} | {nome} | {site} | {telefone} | {instagram} |")

    return "\n".join(lines)


def _leads_to_csv_content(leads: list[dict]) -> str:
    """Converte lista de leads em string CSV."""
    lines = ["Nome,Site,Telefone,Instagram,Fonte"]
    for lead in leads:
        nome = lead.get("nome", "").replace('"', '""')
        site = lead.get("site", "")
        telefone = lead.get("telefone", "")
        instagram = lead.get("instagram", "")
        fonte = lead.get("fonte", "")
        lines.append(f'"{nome}","{site}","{telefone}","{instagram}","{fonte}"')
    return "\n".join(lines)


# ── Execucao ───────────────────────────────────────────────────────────────────

async def execute(args: dict) -> str:
    """
    Busca leads de empresas a partir de nicho + localizacao.

    Args:
        args["niche"]: tipo de empresa
        args["location"]: cidade/regiao
        args["platform"]: google_maps, instagram ou web
        args["max_results"]: limite de resultados

    Returns:
        Tabela Markdown com leads + CSV embutido para download
    """
    import asyncio

    niche = args.get("niche", "").strip()
    location = args.get("location", "").strip()
    platform = args.get("platform", "web").strip().lower()
    max_results = min(int(args.get("max_results", 20)), 50)

    if not niche:
        return "Erro: informe o nicho (tipo de empresa) a buscar."
    if not location:
        return "Erro: informe a localizacao (cidade/regiao)."

    logger.info("[LEADS] Buscando %d leads: '%s' em '%s' (plataforma: %s)", max_results, niche, location, platform)

    # ── Gera e executa script no E2B sandbox ───────────────────────────────────
    script = _build_search_script(niche, location, platform, max_results)

    try:
        from e2b_code_interpreter import Sandbox
    except ImportError:
        return "Erro: pacote e2b-code-interpreter nao instalado. Execute: pip install e2b-code-interpreter"

    # Busca chave E2B
    e2b_key = os.getenv("E2B_API_KEY")
    if not e2b_key:
        try:
            from backend.core.config import get_config
            config = get_config()
            e2b_key = config.e2b_api_key
        except Exception:
            pass
    if not e2b_key:
        try:
            from backend.core.supabase_client import get_supabase_client
            db = get_supabase_client()
            for provider in ("e2b", "e2b_api_key"):
                rows = db.query("ApiKeys", "api_key", {"provider": provider})
                if rows and rows[0].get("api_key"):
                    e2b_key = rows[0]["api_key"]
                    break
        except Exception:
            pass

    if not e2b_key:
        return "Erro: E2B_API_KEY nao configurada."

    def _run_in_sandbox():
        sandbox = Sandbox.create(api_key=e2b_key)
        try:
            result = sandbox.run_code(script)
            parts = []
            if result.logs and result.logs.stdout:
                parts.append("".join(result.logs.stdout))
            if result.text:
                parts.append(result.text)
            if result.error:
                parts.append(f"ERRO: {result.error.name}: {result.error.value}")
            if result.logs and result.logs.stderr:
                stderr_text = "".join(result.logs.stderr)
                # Filtra warnings de pip
                important = [l for l in stderr_text.split("\n") if "ERROR" in l.upper() or "Exception" in l]
                if important:
                    parts.append("STDERR: " + "\n".join(important))
            return "\n".join(parts)
        finally:
            sandbox.kill()

    try:
        output = await asyncio.to_thread(_run_in_sandbox)
    except Exception as e:
        logger.error("[LEADS] Falha no sandbox E2B: %s", e)
        return f"Erro ao executar busca de leads: {e}"

    # ── Parse e formata resultado ──────────────────────────────────────────────
    leads = _parse_leads_from_output(output)

    if not leads:
        # Tenta fallback: se sandbox retornou erro, reporta
        if "ERRO" in output:
            return f"A busca encontrou um problema:\n{output[:500]}\n\nTente com termos diferentes ou outra plataforma."
        return (
            f"Nenhum lead encontrado para '{niche}' em '{location}'. "
            "Tente ampliar o nicho ou mudar a localizacao."
        )

    logger.info("[LEADS] %d leads encontrados para '%s' em '%s'", len(leads), niche, location)

    # Tabela Markdown
    table = _leads_to_markdown_table(leads)

    # CSV para download
    csv_content = _leads_to_csv_content(leads)

    # Tenta fazer upload do CSV para Supabase
    csv_url = ""
    try:
        import time as _time
        from backend.core.supabase_client import upload_to_supabase
        from backend.core.config import get_config
        config = get_config()
        filename = f"leads_{niche.replace(' ', '_')}_{location.replace(' ', '_')}_{int(_time.time())}.csv"
        csv_url = upload_to_supabase(
            config.supabase_storage_bucket,
            filename,
            csv_content.encode("utf-8"),
            "text/csv",
        )
    except Exception as e:
        logger.warning("[LEADS] Falha ao fazer upload CSV: %s", e)

    # Monta resultado final
    result = f"Encontrei {len(leads)} leads de '{niche}' em '{location}':\n\n{table}"

    if csv_url:
        result += f"\n\nCSV para download: [{csv_url}]({csv_url})"
    else:
        result += "\n\nCSV_DATA_START\n" + csv_content + "\nCSV_DATA_END"

    return result
