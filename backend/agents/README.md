> Para visão arquitetural operacional, leia também `docs/architecture/ai-maintenance-guide.md`.

# Backend Agents

Este diretório concentra a orquestração agentica do Arcco.

## Fonte de verdade
- Catálogo de capabilities: `backend/agents/capabilities.py`
- Contratos tipados: `backend/agents/contracts.py`
- Task types: `backend/agents/task_types.py`
- Dispatcher: `backend/agents/dispatcher.py`
- Orquestrador: `backend/agents/orchestrator.py`
- Validadores: `backend/agents/validators.py`
- Clarificação: `backend/agents/clarifier.py`
- Workflow policy: `backend/agents/workflow_policy.py`
- Replanejamento por step: `backend/agents/step_replanner.py`
- Workflow stages: `backend/agents/workflow_state.py`

## Modelo mental atual
- `chat` conversa com o usuário e coordena a execução.
- `planner` quebra tarefas complexas em steps mínimos.
- `dispatcher` executa capabilities diretas.
- `validators` conferem consistência sem bloquear entrega.
- `workflow_policy` decide retry, continuação parcial ou clarificação.
- `step_replanner` troca de route quando existe alternativa compatível.

## Regra prática
O que é comportamental e canônico deve estar descrito em capability, contract, task type, policy ou workflow state.

O que não deve acontecer:
- comportamento relevante escondido só em comentário
- fluxo novo implementado só no prompt
- troca de route implícita sem trilha de log
- dado crítico passado entre steps apenas em linguagem natural
