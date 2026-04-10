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

    if "missing_required_session_files" in issue_codes:
        return [
            _choice_question(
                "Para eu resolver isso, preciso dos arquivos citados. Como você quer seguir?",
                helper_text="Sem os anexos corretos, eu não consigo extrair texto, imagens ou reconstruir o material com fidelidade.",
                options=[
                    ("Vou enviar os arquivos agora", "Melhor caminho para continuar com precisão.", True),
                    ("Quero testar com um arquivo primeiro", "Permite validar o fluxo com uma amostra.", False),
                    ("Prefiro alinhar o formato antes", "Define o entregável antes de subir os anexos.", False),
                ],
            )
        ]

    if "session_files_not_ready" in issue_codes:
        return [
            _choice_question(
                "Os anexos ainda estão processando. O que você prefere?",
                helper_text="OCR e extração podem levar alguns segundos dependendo do tamanho dos arquivos.",
                options=[
                    ("Esperar e continuar quando estiver pronto", "Mantém o fluxo com os arquivos reais.", True),
                    ("Seguir só com estrutura preliminar", "Mais rápido, mas sem conteúdo fiel do anexo.", False),
                    ("Cancelar por enquanto", "Interrompe o fluxo até os arquivos estarem prontos.", False),
                ],
            )
        ]

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

    if "missing_required_user_inputs" in issue_codes:
        return [
            _choice_question(
                "Você quer um destino específico ou uma comparação mais ampla?",
                helper_text="Isso define se a coleta deve focar precisão ou cobertura.",
                options=[
                    ("Destino específico", "Melhor para preços comparáveis e precisos.", True),
                    ("Comparar capitais principais", "Mostra uma visão ampla da categoria.", False),
                    ("Menor preço em qualquer destino", "Prioriza economia, não destino.", False),
                ],
            ),
            _choice_question(
                "Qual recorte de datas devo usar?",
                helper_text="Buscar o mês inteiro pode deixar os resultados rasos demais.",
                options=[
                    ("Primeira quinzena", "Ajuda a filtrar melhor as tarifas.", True),
                    ("Segunda quinzena", "Mantém foco na metade final do mês.", False),
                    ("Mês inteiro", "Mais amplo, mas menos preciso.", False),
                ],
            ),
            _choice_question(
                "Qual padrão de viagem você quer comparar?",
                helper_text="Isso muda bastante preço, duração e quantidade de opções.",
                options=[
                    ("Econômica com escalas", "Maior cobertura e menor preço.", True),
                    ("Econômica com menos escalas", "Equilíbrio entre preço e conveniência.", False),
                    ("Executiva", "Comparação premium.", False),
                ],
            ),
        ]

    if "browser_collection_recommended" in issue_codes:
        return [
            _choice_question(
                "Para ficar mais preciso, posso abrir sites e preencher filtros de busca?",
                helper_text="Isso melhora preços, datas e comparações quando a busca textual é rasa.",
                options=[
                    ("Sim, buscar com navegador", "Mais preciso para preço e disponibilidade.", True),
                    ("Não, seguir só com busca textual", "Mais rápido, mas menos detalhado.", False),
                    ("Entregar parcial agora", "Entrega o que já foi encontrado.", False),
                ],
            )
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

    if task_type == "open_problem_solving":
        return [
            _choice_question(
                "Qual é o entregável final que você quer primeiro?",
                helper_text="Isso ajuda o agente a decidir entre Python, design, edição de arquivo ou combinação dessas rotas.",
                options=[
                    ("Novo PDF", "Prioriza reconstrução e exportação final do documento.", True),
                    ("HTML editável", "Bom para validar layout e estrutura antes de exportar.", False),
                    ("Resumo estruturado", "Útil para validar o conteúdo antes do artefato final.", False),
                ],
            ),
            _choice_question(
                "O que eu devo preservar com mais fidelidade?",
                helper_text="Isso define o que pode ser transformado e o que precisa ficar mais próximo do original.",
                options=[
                    ("Texto e imagens", "Mantém o conteúdo principal mesmo com reorganização.", True),
                    ("Layout original", "Prioriza aparência e posição dos elementos.", False),
                    ("Só o conteúdo essencial", "Permite simplificar e reconstruir.", False),
                ],
            ),
            _choice_question(
                "Posso usar etapas intermediárias para resolver melhor?",
                helper_text="Exemplo: extrair, gerar código Python, montar HTML e depois exportar o arquivo final.",
                options=[
                    ("Sim, pode iterar livremente", "Melhor para tarefas singulares e compostas.", True),
                    ("Prefiro o caminho mais direto", "Menos etapas, mesmo com menos flexibilidade.", False),
                    ("Quero validar antes do arquivo final", "Mostra uma etapa intermediária primeiro.", False),
                ],
            ),
        ]

    return []
