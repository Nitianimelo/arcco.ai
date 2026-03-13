"""
Orquestrador Multi-Agente do Arcco (Arquitetura Supervisor-Worker / ReAct).

Fluxo de execução:
  1. O Agente Supervisor (único a conversar com o usuário) recebe a requisição.
  2. O Supervisor decide se responde diretamente ou se usa Ferramentas (Sub-Agentes).
  3. Ao usar uma Ferramenta Não-Terminal (Busca, Arquivos):
      - O sub-agente executa a tarefa.
      - O Agente QA revisa (máx 2 tentativas) — apenas para rotas de arquivo.
      - O resultado volta para o Supervisor redigir a resposta final amigável.
  4. Ao usar uma Ferramenta Terminal (Design, Text Generator):
      - O sub-agente executa a tarefa.
      - O resultado bruto (HTML/texto) é enviado diretamente ao usuário via SSE.
      - O loop do Supervisor é encerrado imediatamente (proteção do Front-end).
  5. Ferramentas diretas (web_search, execute_python):
      - Executadas diretamente pelo executor, resultado volta ao Supervisor.
"""

import asyncio
import json
import logging
import re
from typing import AsyncGenerator

from backend.core.llm import call_openrouter, stream_openrouter
from backend.agents import registry
from backend.agents.executor import execute_tool

logger = logging.getLogger(__name__)

# ── Mapa de Ferramentas do Supervisor ────────────────────────────────────────

TOOL_MAP = {
    "read_session_file": {"route": "session_file", "is_terminal": False},
    "ask_text_generator": {"route": "text_generator", "is_terminal": True},
    "ask_design_generator": {"route": "design_generator", "is_terminal": True},
    "ask_file_modifier": {"route": "file_modifier", "is_terminal": False},
    "ask_browser": {"route": "browser", "is_terminal": False},
    "ask_web_search": {"route": "web_search", "is_terminal": False},
    "execute_python": {"route": "python", "is_terminal": False},
    "deep_research": {"route": "deep_research", "is_terminal": False},
}

# Rotas que DEVEM conter links de download
ROUTES_REQUIRING_LINK = {"file_modifier"}
_MARKDOWN_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\((https?://[^\)]+)\)', re.IGNORECASE)

# ── Utilitários SSE ──────────────────────────────────────────────────────────

def sse(event_type: str, content: str) -> str:
    return f'data: {{"type": "{event_type}", "content": {json.dumps(content)}}}\n\n'


def _extract_markdown_links(content: str) -> list[tuple[str, str]]:
    return _MARKDOWN_LINK_PATTERN.findall(content or "")


def _artifact_payload(label: str, url: str) -> str:
    return json.dumps({"filename": label, "url": url})


async def _emit_file_artifacts(content: str) -> AsyncGenerator[str, None]:
    md_links = _extract_markdown_links(content)
    if not md_links:
        return

    for label, url in md_links:
        yield sse("file_artifact", _artifact_payload(label, url))


async def _stream_assistant_text(messages: list, model: str) -> AsyncGenerator[str, None]:
    accumulated = ""
    async for chunk in stream_openrouter(
        messages=messages,
        model=model,
        max_tokens=4096,
        temperature=0.7,
    ):
        if "choices" not in chunk or not chunk["choices"]:
            continue
        delta = chunk["choices"][0].get("delta", {})
        content = delta.get("content")
        if not content:
            continue
        accumulated += content
        yield sse("chunk", content)

    if not accumulated:
        yield sse("chunk", "Desculpe, não consegui gerar uma resposta. Tente novamente.")


def _build_session_inventory_message(session_id: str | None) -> str | None:
    if not session_id:
        return None

    try:
        from backend.services.session_file_service import get_session_inventory, touch_session

        touch_session(session_id)
        inventory = get_session_inventory(session_id)
        if not inventory:
            return f"Arquivos anexados nesta sessão ({session_id}): nenhum arquivo disponível."

        items = ", ".join(
            f"{item['file_name']} ({item['status']})"
            for item in inventory
            if item.get("file_name")
        )
        return (
            f"Arquivos anexados nesta sessão ({session_id}): {items}. "
            "Consulte o conteúdo desses anexos EXCLUSIVAMENTE com a ferramenta read_session_file."
        )
    except Exception as exc:
        logger.error("Falha ao montar inventário da sessão %s: %s", session_id, exc)
        return None


# ── Agente QA ────────────────────────────────────────────────────────────────

async def _qa_review(
    user_intent: str, specialist_response: str, route: str, model: str
) -> dict:
    """Revisa a resposta do especialista. Retorna {approved, issues, correction_instruction}."""
    try:
        review_prompt = (
            f"Pedido original: {user_intent}\n"
            f"Tipo esperado: {route}\n\n"
            f"Resposta do especialista:\n{specialist_response[:3000]}"
        )
        data = await call_openrouter(
            messages=[
                {"role": "system", "content": registry.get_prompt("qa")},
                {"role": "user", "content": review_prompt},
            ],
            model=registry.get_model("qa") or model,
            max_tokens=300,
            temperature=0.1,
        )
        raw = data["choices"][0]["message"]["content"].strip()
        raw = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"[QA] Erro na revisão: {e}")
        return {"approved": True, "issues": []}  # Fail-open


# ── Validação Anti-Alucinação ────────────────────────────────────────────────

_URL_PATTERN = re.compile(r'https?://[^\s\)\]"\'>]+', re.IGNORECASE)
_DOC_TAG_RE = re.compile(r'<doc\s+title="([^"]+)">([\s\S]*?)</doc>', re.DOTALL)


def _extract_urls_from_tool_history(messages: list) -> list[str]:
    """
    Extrai URLs de download do histórico de tool results.
    Isso funciona independente do que o LLM decidir dizer —
    os links gerados pelo executor (Supabase upload) são determinísticos.
    """
    urls = []
    for msg in messages:
        if msg.get("role") == "tool":
            content = str(msg.get("content", ""))
            md_links = _MARKDOWN_LINK_PATTERN.findall(content)
            if md_links:
                urls.extend(url for _, url in md_links)
            else:
                raw_urls = _URL_PATTERN.findall(content)
                urls.extend(url for url in raw_urls if 'supabase' in url or 'storage' in url)
    return urls


def _validate_specialist_response(response: str, route: str, tool_messages: list) -> str:
    """
    Valida e corrige a resposta do especialista.
    Se a rota exige link de download e o LLM alucinhou (não incluiu), injeta o link real.
    """
    if route not in ROUTES_REQUIRING_LINK:
        return response

    has_link = bool(_MARKDOWN_LINK_PATTERN.search(response))
    if has_link:
        return response

    urls = _extract_urls_from_tool_history(tool_messages)
    if urls:
        url = urls[-1]
        ext = url.rsplit('.', 1)[-1].split('?')[0].upper() if '.' in url else 'Arquivo'
        link_label = f"Baixar {ext}" if ext in ('PDF', 'XLSX', 'PPTX', 'DOCX') else "Baixar Arquivo"
        logger.warning(f"[ANTI-HALLUCINATION] Especialista não incluiu link. Injetando: {url[:60]}...")
        response += f"\n\n[{link_label}]({url})"
    else:
        logger.error(f"[ANTI-HALLUCINATION] Nenhum link encontrado nos tool results para rota '{route}'")

    return response


# ── Loops dos Especialistas (Sub-Agentes) ────────────────────────────────────

async def _run_specialist_with_tools(
    messages: list,
    model: str,
    system_prompt: str,
    tools: list,
    max_iterations: int = 5,
    thought_log: list | None = None,
) -> str:
    """
    Executa especialista com ferramentas. Retorna resposta final como string.
    Se thought_log for passado, acumula nele o raciocínio do especialista.
    """
    current = [{"role": "system", "content": system_prompt}, *messages]

    for _ in range(max_iterations):
        data = await call_openrouter(
            messages=current,
            model=model,
            max_tokens=4096,
            tools=tools if tools else None,
        )
        message = data["choices"][0]["message"]
        current.append(message)

        if message.get("tool_calls"):
            if thought_log is not None:
                intermediate_thought = (message.get("content") or "").strip()
                if intermediate_thought:
                    thought_log.append(intermediate_thought)

            for tool in message["tool_calls"]:
                func_name = tool["function"]["name"]
                try:
                    func_args = json.loads(tool["function"]["arguments"])
                    result = await execute_tool(func_name, func_args)
                except json.JSONDecodeError:
                    result = "Erro: Argumentos da ferramenta com JSON inválido. Corrija a formatação JSON e tente novamente."
                except Exception as e:
                    result = f"Erro na execução da ferramenta: {e}"

                current.append({
                    "role": "tool",
                    "tool_call_id": tool["id"],
                    "content": str(result),
                })
        else:
            return message.get("content", "")

    return "Limite de iterações atingido no Especialista."


async def _run_terminal_one_shot(
    messages: list,
    model: str,
    system_prompt: str,
    tools: list,
) -> str:
    """
    Agente terminal com suporte a UMA chamada de ferramenta.
    Fluxo otimizado (evita a 3ª chamada ao LLM).
    """
    current = [{"role": "system", "content": system_prompt}, *messages]

    data = await call_openrouter(
        messages=current,
        model=model,
        max_tokens=6000,
        tools=tools if tools else None,
    )
    message = data["choices"][0]["message"]

    if not message.get("tool_calls"):
        return message.get("content", "")

    tool = message["tool_calls"][0]
    func_name = tool["function"]["name"]
    try:
        func_args = json.loads(tool["function"]["arguments"])
        result = await execute_tool(func_name, func_args)
    except json.JSONDecodeError:
        result = "Erro: argumentos JSON inválidos na ferramenta. Tente novamente."
    except Exception as e:
        result = f"Erro ao executar '{func_name}': {e}"

    return result


async def _run_specialist_with_qa(
    route: str, user_intent: str, temp_messages: list, model: str, custom_step_msg: str
) -> AsyncGenerator[str, None]:
    """
    Executa o Especialista + QA + Validação Anti-Alucinação.
    Yields SSE steps para a UI, e no final yielda 'RESULT:' com a resposta validada.
    """
    MAX_QA_RETRIES = 2
    specialist_response = ""
    current_messages = list(temp_messages)

    for attempt in range(MAX_QA_RETRIES + 1):
        if attempt == 0:
            yield sse("steps", f"<step>{custom_step_msg}</step>")
        else:
            yield sse("steps", "<step>Aperfeiçoando qualidade do resultado...</step>")

        thought_log: list[str] = []
        try:
            specialist_response = await _run_specialist_with_tools(
                current_messages,
                registry.get_model(route) or model,
                registry.get_prompt(route),
                registry.get_tools(route),
                thought_log=thought_log,
            )
        except Exception as e:
            logger.error(f"[SPECIALIST] Erro na execução do especialista '{route}': {e}")
            yield f"RESULT:Erro ao processar especialista: {e}"
            return

        for thought in thought_log:
            yield sse("thought", thought)

        specialist_response = _validate_specialist_response(
            specialist_response, route, current_messages
        )

        # QA Review
        yield sse("steps", "<step>Validando qualidade do resultado...</step>")
        qa_result = await _qa_review(user_intent, specialist_response, route, model)

        if qa_result.get("approved", True):
            break

        if attempt < MAX_QA_RETRIES:
            correction = qa_result.get("correction_instruction", "Corrija a resposta.")
            current_messages = current_messages + [
                {"role": "assistant", "content": specialist_response},
                {"role": "user", "content": f"[QA Feedback] {correction}"},
            ]
        else:
            yield sse("steps", "<step>Preparando melhor resultado disponível...</step>")

    yield f"RESULT:{specialist_response}"


# ── Pipeline Principal (Supervisor ReAct) ────────────────────────────────────

async def orchestrate_and_stream(
    messages: list,
    model: str,
    session_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Pipeline ReAct (Supervisor-Worker) + Roteamento Dinâmico.
    1. Executa o Planner para gerar um plano determinístico JSON.
    2. Itera sobre o plano se for complexo.
       - Passa o `step_context` (resultado do passo anterior) para cada passo logando com clareza.
    """

    from backend.agents.tools import SUPERVISOR_TOOLS
    from backend.agents.planner import generate_plan

    supervisor_prompt = registry.get_prompt("chat")
    supervisor_model = registry.get_model("chat") or model
    session_inventory_message = _build_session_inventory_message(session_id)

    user_intent = next(
        (str(m["content"]) for m in reversed(messages) if m.get("role") == "user"), ""
    )

    planner_model = registry.get_model("planner") or supervisor_model

    yield sse("steps", "<step>A estruturar plano de execução...</step>")

    # ── 1. Planejamento (Planner Output Estruturado — modelo leve) ──
    yield sse("thought", "Analisando a complexidade do pedido e decidindo a sequência de ações...")
    plan_output = await generate_plan(user_intent, planner_model)
    
    if plan_output.is_complex and plan_output.steps:
        yield sse("steps", f"<step>Plano gerado: {len(plan_output.steps)} passos identificados.</step>")
        
        # O contexto acumulado que será passado de um agente para outro
        accumulated_context = ""
        final_answer = ""
        
        # ── 2. Iteração do Plano ──
        for step in plan_output.steps:
            yield sse("steps", f"<step>Passo {step.step}/{len(plan_output.steps)}: {step.detail[:50]}...</step>")
            yield sse("thought", f"Iniciando ação '{step.action}': {step.detail}")
            
            # Constrói temporariamente as mensagens injetando o contexto do passo anterior
            step_messages = [{"role": "system", "content": supervisor_prompt}]
            if session_inventory_message:
                step_messages.append({"role": "system", "content": session_inventory_message})
            step_messages += messages
            
            # Adiciona o contexto prévio ao LLM no momento da chamada da ferramenta
            execution_prompt = f"Seu objetivo atual: {step.detail}\n"
            if accumulated_context:
                execution_prompt += f"\nContexto prévio de passos anteriores (USE ESTES DADOS):\n{accumulated_context}"
            
            step_messages.append({"role": "user", "content": execution_prompt})
            
            # Mapa de ação do Planner → nome da ferramenta do Supervisor.
            # Isso garante que o Supervisor chame a ferramenta certa para cada passo,
            # evitando que o LLM substitua ask_browser por ask_web_search, por exemplo.
            _PLANNER_ACTION_TO_TOOL = {
                "browser":        "ask_browser",
                "web_search":     "ask_web_search",
                "python":         "execute_python",
                "deep_research":  "deep_research",
                "file_modifier":  "ask_file_modifier",
                "text_generator": "ask_text_generator",
                "design_generator": "ask_design_generator",
            }
            _forced_tool_name = _PLANNER_ACTION_TO_TOOL.get(step.action)
            _tool_choice = (
                {"type": "function", "function": {"name": _forced_tool_name}}
                if _forced_tool_name
                else "auto"
            )

            try:
                data = await call_openrouter(
                    messages=step_messages,
                    model=supervisor_model,
                    max_tokens=4096,
                    tools=SUPERVISOR_TOOLS,
                    tool_choice=_tool_choice,
                )
                message = data["choices"][0]["message"]
            except Exception as e:
                logger.error(f"[ORCHESTRATOR] Erro no LLM (Passo {step.step}): {e}")
                yield sse("error", f"Erro ao processar o Passo {step.step}: {e}")
                return
                
            # Tratamento da resposta do Supervisor / Tool Call
            if message.get("tool_calls"):
                for tool in message["tool_calls"]:
                    func_name = tool["function"]["name"]
                    try:
                        func_args = json.loads(tool["function"]["arguments"])
                    except json.JSONDecodeError:
                        yield sse("steps", "<step>Erro de argumentos sub-agente. Ignorando...</step>")
                        continue

                    if func_name not in TOOL_MAP:
                        continue
                        
                    route = TOOL_MAP[func_name]["route"]
                    is_terminal = TOOL_MAP[func_name]["is_terminal"]
                    recent_context = [m for m in step_messages if m.get("role") in ["user", "assistant"]][-5:]
                    
                    # ── try/except protege cada tool para que um erro não mate o pipeline ──
                    try:

                        if route == "session_file":
                            specialist_result = await execute_tool("read_session_file", func_args)
                            accumulated_context += f"\n[Passo {step.step} - session_file]: {specialist_result}"
                            yield sse(
                                "thought",
                                f"Arquivo de sessão consultado: {func_args.get('file_name', '')}",
                            )

                        elif route == "web_search":
                            query = func_args.get("query", "")
                            specialist_result = await execute_tool("web_search", {"query": query})
                            accumulated_context += f"\n[Passo {step.step} - web_search]: {specialist_result}"
                            yield sse("thought", f"Dados obtidos da web via busca: {query}")

                        elif route == "python":
                            specialist_result = await execute_tool("execute_python", func_args)
                            accumulated_context += f"\n[Passo {step.step} - python]: {specialist_result}"
                            yield sse("thought", f"Resultado do código Python: {specialist_result[:120]}...")

                        elif route == "browser":
                            url = func_args.get("url", "")
                            raw_actions = func_args.get("actions", [])

                            action_types = [a.get("type", "?") for a in raw_actions if isinstance(a, dict)]
                            yield sse("browser_action", json.dumps({
                                "status": "navigating",
                                "url": url,
                                "title": f"Acessando {url[:60]}...",
                                "actions": action_types
                            }))

                            yield sse("thought", f"Iniciando motor de navegação headless em {url}...")
                            if action_types:
                                yield sse("thought", f"Aplicando ações de interação na página: {', '.join(action_types)}")
                            else:
                                yield sse("thought", "Lendo a estrutura do DOM e extraindo o conteúdo principal...")

                            specialist_result = await execute_tool("ask_browser", func_args)

                            if specialist_result.startswith("Erro"):
                                yield sse("browser_action", json.dumps({
                                    "status": "error",
                                    "url": url,
                                    "title": specialist_result[:100]
                                }))
                                yield sse("thought", f"Falha ao extrair dados de {url}. Ajustando rota...")
                                accumulated_context += f"\n[Passo {step.step} - browser]: Falha ao acessar {url}: {specialist_result}"
                            else:
                                yield sse("browser_action", json.dumps({
                                    "status": "done",
                                    "url": url,
                                    "title": "Página lida com sucesso"
                                }))
                                yield sse("thought", f"Extração de {url} concluída com sucesso. Analisando dados...")
                                accumulated_context += f"\n[Passo {step.step} - browser]: {specialist_result}"
                        
                        elif route == "deep_research":
                            from backend.agents.deep_research import run_deep_research
                            research_query = func_args.get("query", "")
                            research_result = ""
                            async for event in run_deep_research(research_query, supervisor_model, accumulated_context):
                                if event.startswith("RESULT:"):
                                    research_result = event[7:]
                                else:
                                    yield event
                            accumulated_context += f"\n[Passo {step.step} - deep_research]: {research_result}"

                        elif is_terminal:
                            # Rota Terminal encerra o loop enviando direto à UI
                            if route == "text_generator":
                                content = f"Título sugerido: {func_args.get('title_hint', '')}\nContexto Prédio: {accumulated_context}\nInstruções: {func_args.get('instructions', '')}"
                            elif route == "design_generator":
                                content = f"Contexto Prévio:\n{accumulated_context}\n\nInstruções: {func_args.get('instructions', '')}"
                            else:
                                content = json.dumps(func_args)

                            temp_msgs = recent_context + [{"role": "user", "content": content}]
                            route_prompt = registry.get_prompt(route)
                            route_model = registry.get_model(route) or supervisor_model
                            route_tools = registry.get_tools(route)

                            final_result = await _run_terminal_one_shot(temp_msgs, route_model, route_prompt, route_tools)

                            if route == "text_generator":
                                doc_match = _DOC_TAG_RE.search(final_result)
                                if doc_match:
                                    doc_title = doc_match.group(1).strip()
                                    doc_content = doc_match.group(2).strip()
                                    yield sse("text_doc", json.dumps({"title": doc_title, "content": doc_content}))
                                    final_result = _DOC_TAG_RE.sub(doc_content, final_result)

                            chunk_size = 40
                            for i in range(0, len(final_result), chunk_size):
                                yield sse("chunk", final_result[i:i + chunk_size])

                            # Já enviou pro usuário, termina por aqui
                            return
                        else:
                            # File Modifier (Não-Terminal)
                            file_url = func_args.get("file_url")
                            session_ref = ""
                            if func_args.get("session_id") and func_args.get("file_name"):
                                session_ref = (
                                    f"Sessão: {func_args.get('session_id')} "
                                    f"Arquivo da sessão: {func_args.get('file_name')}\n"
                                )
                            content = (
                                f"Contexto: {accumulated_context}\n"
                                f"Arquivo remoto: {file_url or 'N/A'}\n"
                                f"{session_ref}"
                                f"Instruções: {func_args.get('instructions')}"
                            )
                            temp_msgs = recent_context + [{"role": "user", "content": content}]
                            specialist_result = ""
                            async for event in _run_specialist_with_qa(route, user_intent, temp_msgs, supervisor_model, f"Modificando arquivo (Passo {step.step})..."):
                                if event.startswith("RESULT:"):
                                    specialist_result = event[7:]
                                else:
                                    yield event

                            # ANTI-LEAK
                            if route in ROUTES_REQUIRING_LINK:
                                md_links = _extract_markdown_links(specialist_result)
                                if md_links:
                                    for label, url in md_links:
                                        yield sse("file_artifact", _artifact_payload(label, url))
                                    links_only = "\n".join(f"[{label}]({url})" for label, url in md_links)
                                    specialist_result = f"Arquivo gerado.\n\n{links_only}"

                            accumulated_context += f"\n[Passo {step.step} - file_modifier]: {specialist_result}"

                    except Exception as tool_exc:
                        # Captura qualquer erro (ImportError, timeout, etc.) sem matar o pipeline
                        logger.error(f"[ORCHESTRATOR] Erro na tool '%s' (Passo %s): %s", func_name, step.step, tool_exc)
                        error_msg = f"Ferramenta '{func_name}' falhou: {tool_exc}"
                        accumulated_context += f"\n[Passo {step.step} - ERRO {route}]: {error_msg}"
                        yield sse("thought", f"Erro no passo {step.step}: {error_msg}")

            else:
                # O LLM decidiu não usar TOOL, apenas gerou texto
                accumulated_context += f"\n[Passo {step.step} - raciocínio]: {message.get('content', '')}"
                
        # Fim do loop do Planner
        # Agora geramos a resposta final conversacional consolidando o accumulated_context
        yield sse("steps", "<step>Consolidando resultados dos passos...</step>")
        
        final_prompt = [
            {"role": "system", "content": supervisor_prompt},
            *(
                [{"role": "system", "content": session_inventory_message}]
                if session_inventory_message
                else []
            ),
            {"role": "user", "content": f"Pedido inicial: {user_intent}\n\nExecutei um plano de vários passos e recolhi o seguinte histórico/resultados:\n{accumulated_context}\n\nPor favor, escreva a resposta final amigável e conclusiva para o utilizador, incluindo todos os links de arquivos ou sumários relevantes obtidos nos passos."}
        ]
        
        try:
            async for event in _stream_assistant_text(final_prompt, supervisor_model):
                yield event
        except Exception as exc:
            logger.error("[ORCHESTRATOR] Erro no streaming final consolidado: %s", exc)
            fallback_text = accumulated_context or "Desculpe, não consegui consolidar a resposta final."
            yield sse("chunk", fallback_text)

        return

    # ── 3. Fallback / Sem Planejamento Complexo (Execução Normal ReAct) ──
    yield sse("thought", "Pedido direto. Respondendo ou acionando a ferramenta aplicável.")
    current_messages = [{"role": "system", "content": supervisor_prompt}]
    if session_inventory_message:
        current_messages.append({"role": "system", "content": session_inventory_message})
    current_messages += messages
    MAX_ITERATIONS = 5

    for iteration in range(MAX_ITERATIONS):
        if iteration == 0:
            yield sse("steps", "<step>Analisando pedido e planejando execução...</step>")

        # Chama o LLM do Supervisor
        try:
            data = await call_openrouter(
                messages=current_messages,
                model=supervisor_model,
                max_tokens=4096,
                tools=SUPERVISOR_TOOLS
            )
            message = data["choices"][0]["message"]
        except (KeyError, IndexError) as e:
            logger.error(f"[ORCHESTRATOR] Resposta LLM malformada: {e}")
            yield sse("error", "Erro interno ao processar a resposta da IA. Tente novamente.")
            return
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Erro na chamada LLM: {e}")
            yield sse("error", f"Erro ao comunicar com a IA: {e}")
            return

        current_messages.append(message)

        # Emite raciocínio do Supervisor quando ele pensa antes de chamar uma ferramenta
        supervisor_reasoning = (message.get("content") or "").strip()
        if supervisor_reasoning and message.get("tool_calls"):
            yield sse("thought", supervisor_reasoning)

        # ── O Supervisor decidiu usar uma Ferramenta? ────────────────────
        if message.get("tool_calls"):
            for tool in message["tool_calls"]:
                func_name = tool["function"]["name"]

                try:
                    func_args = json.loads(tool["function"]["arguments"])
                except json.JSONDecodeError:
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tool["id"],
                        "content": "Erro sintático no JSON da ferramenta. Corrija a formatação e tente novamente.",
                    })
                    yield sse("steps", "<step>Aguardando sub-agente corrigir os parâmetros da ferramenta...</step>")
                    continue

                if func_name not in TOOL_MAP:
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tool["id"],
                        "content": f"Erro: ferramenta '{func_name}' não suportada pelo orquestrador.",
                    })
                    continue

                route = TOOL_MAP[func_name]["route"]
                is_terminal = TOOL_MAP[func_name]["is_terminal"]

                # Contexto recente para sub-agentes
                recent_context = [m for m in messages if m.get("role") in ["user", "assistant"]][-5:]

                # ── ROTA: Pesquisa Web Rápida (direto, sem sub-agente, sem QA) ──
                if route == "session_file":
                    file_name = func_args.get("file_name", "")
                    yield sse("steps", f"<step>Consultando anexo da sessão: {file_name[:60]}...</step>")
                    specialist_result = await execute_tool("read_session_file", func_args)
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tool["id"],
                        "content": specialist_result,
                    })
                    yield sse("steps", "<step>Leitura do anexo concluída — integrando contexto...</step>")

                elif route == "web_search":
                    query = func_args.get("query", "")
                    fetch_url = func_args.get("fetch_url", "")
                    yield sse("steps", f"<step>Pesquisando: {query[:60]}...</step>")

                    specialist_result = await execute_tool("web_search", {"query": query})

                    if fetch_url:
                        yield sse("steps", f"<step>Lendo página {fetch_url[:50]}...</step>")
                        page_content = await execute_tool("web_fetch", {"url": fetch_url})
                        specialist_result += f"\n\n---\nConteúdo detalhado de {fetch_url}:\n{page_content}"

                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tool["id"],
                        "content": specialist_result,
                    })
                    yield sse("steps", "<step>Dados recebidos — elaborando resposta...</step>")

                # ── ROTA: Execução Python (direto, sem sub-agente, sem QA) ──
                elif route == "python":
                    yield sse("steps", "<step>Executando código Python...</step>")
                    try:
                        specialist_result = await execute_tool("execute_python", func_args)
                    except Exception as exc:
                        logger.error(f"[ORCHESTRATOR] Erro na execução Python: {exc}")
                        specialist_result = f"Erro ao executar Python: {exc}"
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tool["id"],
                        "content": specialist_result,
                    })
                    yield sse("steps", "<step>Código executado — integrando resultado...</step>")

                # ── ROTA: Browser (direto, sem sub-agente, sem QA) ──
                elif route == "browser":
                    url = func_args.get("url", "")
                    raw_actions = func_args.get("actions", [])

                    step_message = f"Abrindo navegador e extraindo dados de {url[:40]}..."
                    if raw_actions:
                        action_types = [a.get("type", "?") for a in raw_actions if isinstance(a, dict)]
                        action_label = ", ".join(action_types)
                        step_message = f"Navegando em {url[:40]}... (ações: {action_label})"

                    yield sse("steps", f"<step>{step_message}</step>")
                    yield sse("browser_action", json.dumps({
                        "status": "navigating",
                        "url": url,
                        "title": f"Acessando {url[:60]}...",
                        "actions": [a.get("type", "?") for a in raw_actions] if raw_actions else []
                    }))

                    try:
                        specialist_result = await execute_tool("ask_browser", func_args)
                    except Exception as exc:
                        logger.error(f"[ORCHESTRATOR] Erro no Browser Agent: {exc}")
                        specialist_result = f"Erro ao executar Browser Agent: {exc}"

                    if specialist_result.startswith("Erro"):
                        yield sse("browser_action", json.dumps({
                            "status": "error",
                            "url": url,
                            "title": specialist_result[:100]
                        }))
                    else:
                        yield sse("browser_action", json.dumps({
                            "status": "done",
                            "url": url,
                            "title": "Página lida com sucesso"
                        }))

                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tool["id"],
                        "content": specialist_result,
                    })
                    yield sse("steps", "<step>Conteúdo extraído — analisando dados...</step>")

                # ── ROTA: Pesquisa Profunda (multi-step, paralelo) ──
                elif route == "deep_research":
                    from backend.agents.deep_research import run_deep_research

                    research_query = func_args.get("query", "")
                    research_context = func_args.get("context", "")
                    yield sse("steps", f"<step>Iniciando pesquisa profunda: {research_query[:60]}...</step>")

                    research_result = ""
                    async for event in run_deep_research(research_query, supervisor_model, research_context):
                        if event.startswith("RESULT:"):
                            research_result = event[7:]
                        else:
                            yield event

                    if not research_result.strip():
                        research_result = "A pesquisa profunda não retornou resultados. Tente reformular o pedido com mais detalhes."

                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tool["id"],
                        "content": research_result,
                    })
                    yield sse("steps", "<step>Pesquisa profunda concluída — preparando resposta...</step>")

                # ── ROTA: Terminal (text_generator, design_generator) ──
                elif is_terminal:
                    if route == "text_generator":
                        step_message = "Estruturando documento bruto e preparando preview..."
                        content = (
                            f"Título sugerido: {func_args.get('title_hint', '')}\n"
                            f"Instruções: {func_args.get('instructions', '')}\n"
                            f"Contexto: {func_args.get('content_brief', '')}"
                        )
                    elif route == "design_generator":
                        step_message = "Construindo design editável e preparando preview..."
                        content = (
                            f"Título sugerido: {func_args.get('title_hint', '')}\n"
                            f"Instruções: {func_args.get('instructions', '')}\n"
                            f"Contexto: {func_args.get('content_brief', '')}\n"
                            f"Direção visual: {func_args.get('design_direction', '')}"
                        )
                    else:
                        step_message = "Processando..."
                        content = json.dumps(func_args)

                    temp_msgs = recent_context + [{"role": "user", "content": content}]

                    yield sse("steps", f"<step>{step_message}</step>")
                    route_prompt = registry.get_prompt(route)
                    route_model = registry.get_model(route) or model
                    route_tools = registry.get_tools(route)

                    final_result = await _run_terminal_one_shot(
                        temp_msgs, route_model, route_prompt, route_tools
                    )

                    if route == "text_generator":
                        doc_match = _DOC_TAG_RE.search(final_result)
                        if doc_match:
                            doc_title = doc_match.group(1).strip()
                            doc_content = doc_match.group(2).strip()
                            yield sse("text_doc", json.dumps({"title": doc_title, "content": doc_content}))
                            final_result = _DOC_TAG_RE.sub(doc_content, final_result)

                    chunk_size = 40
                    for i in range(0, len(final_result), chunk_size):
                        yield sse("chunk", final_result[i:i + chunk_size])

                    # Proteção do frontend: encerra o loop do Supervisor
                    return

                # ── ROTA: Não-terminal com QA (file_modifier) ──
                else:
                    if route == "file_modifier":
                        step_message = "Lendo estrutura do arquivo original e aplicando modificações..."
                        file_url = func_args.get("file_url")
                        session_ref = ""
                        if func_args.get("session_id") and func_args.get("file_name"):
                            session_ref = (
                                f"Sessão: {func_args.get('session_id')} "
                                f"Arquivo da sessão: {func_args.get('file_name')} "
                            )
                        content = (
                            f"Arquivo: {file_url or 'N/A'} "
                            f"{session_ref}"
                            f"Instruções: {func_args.get('instructions')}"
                        )
                    else:
                        step_message = "Processando com especialista..."
                        content = json.dumps(func_args)

                    temp_msgs = recent_context + [{"role": "user", "content": content}]

                    specialist_result = ""
                    async for event in _run_specialist_with_qa(route, user_intent, temp_msgs, model, step_message):
                        if event.startswith("RESULT:"):
                            specialist_result = event[7:]
                        else:
                            yield event

                    if not specialist_result.strip():
                        specialist_result = "O especialista não retornou resultado. Tente reformular o pedido."
                        logger.warning(f"[ORCHESTRATOR] Especialista '{route}' retornou vazio")

                    # ANTI-LEAK: Para rotas de arquivo, enviar APENAS o link pro Supervisor
                    if route in ROUTES_REQUIRING_LINK:
                        md_links = _extract_markdown_links(specialist_result)
                        if md_links:
                            for label, url in md_links:
                                yield sse("file_artifact", _artifact_payload(label, url))
                            links_only = "\n".join(f"[{label}]({url})" for label, url in md_links)
                            specialist_result = f"Arquivo gerado com sucesso.\n\n{links_only}"
                            logger.info("[ANTI-LEAK] Conteúdo suprimido. Apenas link enviado ao Supervisor.")

                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tool["id"],
                        "content": specialist_result,
                    })

                    yield sse("steps", "<step>Integrando resultado do especialista...</step>")

            # Fim do loop de tool_calls, prossegue para o Supervisor responder
            continue

        else:
            # O Supervisor decidiu responder ao usuário diretamente
            yield sse("steps", "<step>Preparando resposta final...</step>")

            content = message.get("content", "")
            doc_match = _DOC_TAG_RE.search(content)
            if doc_match:
                doc_title = doc_match.group(1).strip()
                doc_content = doc_match.group(2).strip()
                yield sse("text_doc", json.dumps({"title": doc_title, "content": doc_content}))
                cleaned_content = _DOC_TAG_RE.sub(doc_content, content)
                if cleaned_content:
                    yield sse("chunk", cleaned_content)
                return

            # A resposta já está em message["content"] — fazemos streaming direto sem segunda chamada LLM.
            final_content = content or "Desculpe, não consegui gerar uma resposta. Tente novamente."
            chunk_size = 40
            for i in range(0, len(final_content), chunk_size):
                yield sse("chunk", final_content[i:i + chunk_size])

            return

    # Se saiu do loop, atingiu MAX_ITERATIONS
    yield sse("error", "Limite máximo de processamento atingido. Por favor, seja mais específico na sua solicitação.")
