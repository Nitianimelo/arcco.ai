"""
Skill: Web Form Operator (RPA)

O usuario fornece uma URL e um dicionario de dados.
A skill acessa a pagina, extrai o HTML do formulario, pede ao LLM
para mapear campos -> dados e gera uma lista de acoes (type/fill/click)
que sao executadas via browser_service.

Fluxo:
  1. Navega ate a URL e extrai o HTML simplificado dos formularios
  2. LLM mapeia form_data nos campos encontrados -> lista de acoes JSON
  3. Executa as acoes no browser (preenche + submete)
"""

import json
import logging
import re

from backend.core.llm import call_openrouter
from backend.agents import registry

logger = logging.getLogger(__name__)

# ── Contrato da Skill ─────────────────────────────────────────────────────────

SKILL_META = {
    "id": "web_form_operator",
    "name": "Preenchimento de Formulario Web",
    "description": (
        "Preenche formularios web de forma autonoma. "
        "O usuario fornece a URL da pagina e os dados a preencher (chave/valor). "
        "A skill navega ate a pagina, mapeia os campos do formulario e executa "
        "as acoes de digitacao e clique automaticamente. "
        "Use para cadastros em CRMs, preenchimento de fichas, envio de formularios online."
    ),
    "keywords": [
        "formulario", "formulário", "preencher", "preenche", "cadastrar", "cadastro",
        "rpa", "form", "crm", "ficha", "registrar", "registro",
    ],
    "parameters": {
        "type": "object",
        "properties": {
            "target_url": {
                "type": "string",
                "description": "URL da pagina que contem o formulario a ser preenchido",
            },
            "form_data": {
                "type": "object",
                "description": (
                    "Dicionario chave/valor com os dados a preencher. "
                    "Ex: {\"nome\": \"Joao Silva\", \"email\": \"joao@email.com\", \"telefone\": \"11999990000\"}"
                ),
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["target_url", "form_data"],
    },
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _simplify_html_for_forms(raw_html: str, max_chars: int = 12000) -> str:
    """Extrai apenas as tags de formulario relevantes do HTML bruto."""
    # Tenta extrair <form>...</form> primeiro
    forms = re.findall(r"<form[\s\S]*?</form>", raw_html, re.IGNORECASE)
    if forms:
        simplified = "\n".join(forms)
    else:
        # Fallback: extrair inputs, selects, textareas, buttons e labels soltos
        tags = re.findall(
            r"<(?:input|select|textarea|button|label|option)[^>]*(?:/>|>[\s\S]*?</(?:select|textarea|button|label)>)",
            raw_html,
            re.IGNORECASE,
        )
        simplified = "\n".join(tags) if tags else raw_html[:max_chars]

    # Limita tamanho para nao estourar contexto do LLM
    if len(simplified) > max_chars:
        simplified = simplified[:max_chars] + "\n<!-- truncado -->"
    return simplified


def _extract_json_from_response(text: str) -> list[dict]:
    """Extrai array JSON da resposta do LLM (tolerante a markdown)."""
    # Remove blocos markdown
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = re.sub(r"```", "", cleaned).strip()

    # Encontra o primeiro array JSON
    match = re.search(r"\[[\s\S]*\]", cleaned)
    if match:
        return json.loads(match.group())
    raise ValueError(f"Nenhum array JSON encontrado na resposta do LLM: {text[:200]}")


# ── Execucao ───────────────────────────────────────────────────────────────────

async def execute(args: dict) -> str:
    """
    Preenche um formulario web autonomamente.

    Args:
        args["target_url"]: URL da pagina com o formulario
        args["form_data"]: dict com os dados a preencher

    Returns:
        Resumo amigavel do resultado
    """
    target_url = args.get("target_url", "").strip()
    form_data = args.get("form_data", {})

    if not target_url:
        return "Erro: URL do formulario nao fornecida."
    if not form_data:
        return "Erro: nenhum dado para preencher foi fornecido."

    logger.info("[RPA] Iniciando preenchimento em %s com %d campos", target_url, len(form_data))

    # ── Passo A: Navegar e extrair HTML do formulario ──────────────────────────
    try:
        from backend.services.browser_service import execute_browserbase_task

        raw_content = await execute_browserbase_task(
            url=target_url,
            actions=[{"type": "scrape"}],
            wait_for=2000,
            include_tags=["form", "input", "select", "textarea", "button", "label"],
        )
    except Exception as e:
        logger.error("[RPA] Falha ao acessar pagina: %s", e)
        return f"Erro ao acessar a pagina: {e}"

    # Extrai HTML puro para enviar ao LLM
    try:
        from backend.services.browser_service import execute_browserbase_task as _bb

        # Faz uma segunda chamada para pegar o HTML bruto via JS
        html_result = await execute_browserbase_task(
            url=target_url,
            actions=[
                {"type": "execute_javascript", "script": "document.documentElement.outerHTML"},
            ],
            wait_for=1000,
        )
    except Exception:
        html_result = raw_content

    form_html = _simplify_html_for_forms(html_result)

    if not form_html or len(form_html) < 20:
        return (
            f"Nao foi possivel encontrar formularios na pagina {target_url}. "
            "Verifique se a URL esta correta e se a pagina contem campos de formulario."
        )

    # ── Passo B: LLM mapeia campos do formulario para os dados ─────────────────
    mapping_prompt = f"""Voce e um especialista em automacao web (RPA).

Analise o HTML de formulario abaixo e os dados fornecidos pelo usuario.
Gere uma lista de acoes para preencher o formulario e submete-lo.

HTML DO FORMULARIO:
{form_html}

DADOS A PREENCHER:
{json.dumps(form_data, ensure_ascii=False, indent=2)}

REGRAS:
1. Para cada campo do formulario, use o seletor CSS mais especifico possivel (id > name > placeholder > type).
2. Use "type": "write" para campos de texto (input, textarea).
3. Use "type": "click" para checkboxes, radio buttons e botoes de submit.
4. Use "type": "press" com "key": "Enter" se nao houver botao de submit visivel.
5. Mapeie os dados para os campos MAIS PROXIMOS semanticamente (ex: "nome" -> campo "name" ou "fullname").
6. Inclua uma acao de submit no final (click no botao ou press Enter).
7. Se um campo do form_data nao tem campo correspondente no formulario, IGNORE-O.

Retorne APENAS um array JSON puro (sem markdown, sem explicacao):
[
  {{"type": "write", "selector": "#campo_id", "text": "valor"}},
  {{"type": "click", "selector": "button[type=submit]"}}
]"""

    try:
        model = registry.get_model("text_generator") or "openai/gpt-4o-mini"
        response = await call_openrouter(
            messages=[{"role": "user", "content": mapping_prompt}],
            model=model,
            max_tokens=2000,
            temperature=0.1,
        )
        llm_text = response["choices"][0]["message"]["content"]
        actions = _extract_json_from_response(llm_text)
    except Exception as e:
        logger.error("[RPA] Falha ao gerar mapeamento de campos: %s", e)
        return f"Erro ao mapear campos do formulario: {e}"

    if not actions:
        return "O LLM nao conseguiu mapear nenhum campo do formulario. Verifique se os dados correspondem aos campos da pagina."

    logger.info("[RPA] %d acoes geradas pelo LLM, executando no browser...", len(actions))

    # ── Passo C: Executar acoes no browser ─────────────────────────────────────
    try:
        result = await execute_browserbase_task(
            url=target_url,
            actions=actions,
            wait_for=2000,
        )
    except Exception as e:
        logger.error("[RPA] Falha ao executar acoes: %s", e)
        return f"Erro ao preencher o formulario: {e}"

    # Monta resumo amigavel
    campos_preenchidos = [a for a in actions if a.get("type") == "write"]
    cliques = [a for a in actions if a.get("type") == "click"]

    resumo = (
        f"Formulario preenchido com sucesso em {target_url}\n\n"
        f"Campos preenchidos: {len(campos_preenchidos)}\n"
        f"Cliques executados: {len(cliques)}\n\n"
        "Detalhes:\n"
    )
    for a in campos_preenchidos:
        resumo += f"  - {a.get('selector', '?')}: \"{a.get('text', '')}\"\n"

    if cliques:
        resumo += f"\nFormulario submetido via: {cliques[-1].get('selector', 'submit')}"

    return resumo
