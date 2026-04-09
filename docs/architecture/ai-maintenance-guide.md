# AI Maintenance Guide

## Objetivo
Este guia existe para reduzir ambiguidade para qualquer IA que precise alterar o backend.

## Fonte de verdade
- Agentes ativos: `backend/agents/registry.py`
- Prompts de sistema: `backend/agents/prompts.py`
- Tools expostas ao LLM: `backend/agents/tools.py`
- Skills dinâmicas: `backend/skills/`
- Catálogo canônico de capabilities: `backend/agents/capabilities.py`
- Contratos tipados mínimos: `backend/agents/contracts.py`
- Tipos de tarefa: `backend/agents/task_types.py`
- Handoffs estruturados entre steps: `backend/agents/handoffs.py`
- Estados de workflow longo: `backend/agents/workflow_state.py`
- Políticas centrais de retry/fallback/clarificação: `backend/agents/workflow_policy.py`
- Replanejamento explícito por step: `backend/agents/step_replanner.py`
- Validadores incrementais: `backend/agents/validators.py`
- Clarificação objetiva: `backend/agents/clarifier.py`
- Logs de execução: `backend/services/execution_log_service.py`

## Conceitos obrigatórios
- `agent`: entidade lógica de decisão ou execução
- `capability`: ação canônica do sistema
- `tool`: interface function-calling exposta ao modelo
- `skill`: plugin dinâmico especializado
- `task`: instância de execução em runtime
- `execution`: execução completa de um pedido do usuário
- `task_type`: classificação canônica do trabalho para logs, validação e políticas
- `validator`: camada que confere a saída sem bloquear a entrega
- `clarifier`: camada que sugere perguntas objetivas quando faltam dados
- `handoff`: payload estruturado que preserva dados críticos entre um step e o próximo
- `policy`: camada que decide retry, continuação parcial, clarificação e aborto do pipeline
- `replan`: camada que troca a capability/route do step quando existe alternativa compatível

## Regras de manutenção
1. Não introduza um novo comportamento sem registrar a capability correspondente.
2. Não use nome de tool como sinônimo automático de route, agent ou skill.
3. Toda mudança de fluxo deve preservar observabilidade no painel admin.
4. Toda execução deve terminar com metadata consolidada em `agent_executions`.
5. Terminalidade deve ser definida de forma consistente entre prompt, capability e runtime.
6. Validação e clarificação devem gerar trilha explícita no painel admin.
7. Browser workflow e mass document analysis devem expor estado operacional e handoff estruturado.

## Anti-padrões
- Resolver semântica de fluxo só no prompt.
- Adicionar exceptions especiais no orquestrador sem registrar no catálogo.
- Retornar strings livres quando o tipo de saída já é conhecido.
- Criar skill nova sem explicar categoria, output e papel no fluxo.
- Passar dados críticos entre steps apenas em linguagem natural quando já existe contrato possível.

## Checklist antes de alterar
1. A capability já existe?
2. O tipo de saída já está descrito?
3. O painel admin continuará conseguindo explicar a execução?
4. A mudança afeta planner, react ou ambos?
5. O handoff humano continua observável?
