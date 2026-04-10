# Context Contracts

## Objetivo
Contrato de contexto é o acordo explícito sobre o que entra e o que sai de uma etapa.

No Arcco, contratos existem para evitar:
- perda de dados entre steps
- reinterpretação livre
- texto bonito escondendo coleta ruim
- fallback implícito difícil de auditar

## Contratos principais

### Planner output
Modelo canônico:
- `PlannerOutputContract`
- `PlanStepContract`
- `ClarificationQuestionContract`

Uso:
- definir steps
- classificar task type
- pedir clarificação antes de executar

Arquivo:
- [backend/agents/contracts.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/contracts.py)

### Capability result
Modelo canônico:
- `CapabilityResult`

Campos centrais:
- `capability_id`
- `route`
- `status`
- `output_type`
- `content`
- `artifacts`
- `handoff_required`
- `error_text`
- `metadata`

Uso:
- normalizar retorno de tool, specialist e fluxo direto
- alimentar validação, logs e admin

### Validation result
Modelo canônico:
- `ValidationResultContract`
- `ValidationIssueContract`

Uso:
- dizer se o output está válido
- apontar gaps
- indicar se precisa clarificação

### Policy decision
Modelo canônico:
- `PolicyDecisionContract`

Uso:
- governar o próximo passo
- decidir retry
- decidir continuação parcial
- decidir clarificação
- decidir aborto

### Route replan
Modelo canônico:
- `RouteReplanDecisionContract`

Uso:
- trocar capability/route sem reexecutar o planner inteiro

### Handoff entre steps
Modelo canônico:
- `StepHandoffContract`
- `ReferenceEntityContract`

Uso:
- preservar dados factuais entre passos
- impedir que o próximo agente reconstrua tudo do zero

## Regra de ouro
Se um dado é importante para o próximo passo, ele deve existir em contrato.

Não dependa apenas de:
- resumo textual
- descrição do step
- boa vontade do próximo modelo

## Exemplos concretos

### Busca -> planilha
Errado:
- `web_search` retorna texto narrativo
- `python` reconstrói entidades lendo esse texto

Certo:
- busca retorna entidades/fontes relevantes
- handoff estrutural preserva entidades
- `python` usa esse payload como referência

### Browser -> síntese
Errado:
- browser falha
- texto final resume como se tivesse dado certo

Certo:
- browser retorna `error_text` ou `handoff_required`
- validator classifica a falha
- policy decide recuperação
- só depois o fluxo chega ao `text_generator`

### Documento massivo
Errado:
- OCR, RAG e resposta final tudo em um bloco implícito

Certo:
- ingestão
- OCR
- index
- goal do usuário
- retrieval
- delivery
- cleanup
tudo com estado e contratos observáveis
