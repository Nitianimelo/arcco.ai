"""
Gerador de perguntas objetivas de clarificação.

Mantém as perguntas curtas, marcáveis e previsíveis para o frontend atual.
"""

from __future__ import annotations

from backend.agents.contracts import (
    ClarificationOptionContract,
    ClarificationQuestionContract,
    TaskTypeId,
    ValidationResultContract,
)


def _choice_question(
    text: str,
    *,
    helper_text: str = "",
    options: list[tuple[str, str, bool]] | None = None,
) -> ClarificationQuestionContract:
    option_details = [
        ClarificationOptionContract(label=label, description=description, recommended=recommended)
        for label, description, recommended in (options or [])
    ]
    return ClarificationQuestionContract(
        type="choice",
        text=text,
        options=[item.label for item in option_details],
        option_details=option_details,
        helper_text=helper_text,
    )


def build_follow_up_questions(
    *,
    task_type: TaskTypeId,
    validation_result: ValidationResultContract,
) -> list[ClarificationQuestionContract]:
    issue_codes = {issue.code for issue in validation_result.issues}

    if "search_to_python_entity_mismatch" in issue_codes:
        return [
            _choice_question(
                "Para completar com mais precisão, qual regra eu devo seguir para escolher os itens da planilha?",
                helper_text="Isso ajuda a manter a planilha fiel à busca, mesmo quando as fontes divergirem.",
                options=[
                    ("Usar só os itens mais citados na busca", "Mantém fidelidade ao resultado principal.", True),
                    ("Priorizar itens com endereço confirmado", "Prefere consistência factual.", False),
                    ("Aceitar itens de Instagram/Facebook se faltarem dados", "Amplia cobertura com fonte social.", False),
                ],
            ),
            _choice_question(
                "Quais campos você quer priorizar na planilha?",
                helper_text="Quanto mais campos obrigatórios, maior a chance de cobertura parcial.",
                options=[
                    ("Nome e endereço", "Mais fácil manter consistente.", True),
                    ("Nome, endereço e telefone", "Melhor para operação comercial.", False),
                    ("Nome, endereço, telefone e Instagram", "Maior cobertura, inclusive com redes sociais.", False),
                ],
            ),
        ]

    if task_type == "browser_workflow" or "browser_handoff_required" in issue_codes:
        return [
            _choice_question(
                "O site pediu uma ação humana. Como você quer seguir?",
                helper_text="Se abrir a sessão ao vivo, a automação pode retomar depois.",
                options=[
                    ("Abrir sessão ao vivo", "Resolve captcha ou bloqueio manualmente.", True),
                    ("Pular esse site", "Entrega parcial, mas segue o fluxo.", False),
                    ("Tentar uma alternativa sem navegador", "Útil quando houver outra fonte.", False),
                ],
            )
        ]

    if task_type == "mass_document_analysis":
        return [
            _choice_question(
                "O que você quer extrair primeiro desse conjunto de documentos?",
                helper_text="Responder isso reduz custo e melhora a precisão do RAG.",
                options=[
                    ("Resumo executivo", "Síntese rápida dos pontos principais.", True),
                    ("Tabela comparativa", "Estrutura os documentos lado a lado.", False),
                    ("Riscos e inconsistências", "Foco em problemas e divergências.", False),
                ],
            )
            ,
            _choice_question(
                "Como você quer receber a primeira saída?",
                helper_text="Isso orienta o formato sem processar conteúdo desnecessário.",
                options=[
                    ("Resumo executivo", "Síntese curta e direta.", True),
                    ("Tabela comparativa", "Estrutura lado a lado os documentos.", False),
                    ("Relatório detalhado", "Aprofunda análise e contexto.", False),
                ],
            )
        ]

    return []
