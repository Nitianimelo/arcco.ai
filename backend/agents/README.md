> Para visão arquitetural operacional, leia também `docs/architecture/ai-maintenance-guide.md`.

# Backend Agents

Este diretório concentra a orquestração agentica do Arcco.

## Fonte de verdade
- Catálogo de capabilities: `backend/agents/capabilities.py`
- Contratos tipados: `backend/agents/contracts.py`
- Task types: `backend/agents/task_types.py`
- Pré-condições: `backend/agents/preconditions.py`
- Dispatcher: `backend/agents/dispatcher.py`
- Orquestrador: `backend/agents/orchestrator.py`
- Validadores: `backend/agents/validators.py`
- Clarificação: `backend/agents/clarifier.py`
- Workflow policy: `backend/agents/workflow_policy.py`
- Replanejamento por step: `backend/agents/step_replanner.py`
- Workflow stages: `backend/agents/workflow_state.py`

## Modelo mental atual
- `chat` e o orquestrador formam o supervisor único da execução.
- pré-condições rodam antes do planner para impedir steps sobre insumos ausentes.
- o planner sugere a estratégia inicial, não governa sozinho o fluxo.
- existem só três engines operacionais:
  - `direct_answer`
  - `structured_run`
  - `open_run`
- `dispatcher` e tools executam.
- `validators` classificam qualidade e erro.
- `workflow_policy` é o árbitro único para continuar, clarificar, retry, replan ou abortar.

## Regra prática
O que é comportamental e canônico deve estar descrito em capability, contract, task type, policy ou workflow state.

O que não deve acontecer:
- comportamento relevante escondido só em comentário
- fluxo novo implementado só no prompt
- troca de route implícita sem trilha de log
- dado crítico passado entre steps apenas em linguagem natural
- planner gerar steps sem que pré-condições básicas tenham sido satisfeitas
- múltiplas camadas decidirem o mesmo fluxo sem precedência explícita
