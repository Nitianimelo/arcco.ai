# Context Engineering

Este repositório usa "engenharia de contexto" como disciplina central de arquitetura.

O objetivo não é apenas montar prompts. O objetivo é controlar, com precisão:
- o que cada etapa sabe
- quando sabe
- em que formato sabe
- o que deve ser preservado entre steps
- o que deve ser descartado
- quando o sistema deve perguntar em vez de inferir
- quando o sistema pode seguir parcial sem inventar

Este arquivo é um ponto de entrada curto. O detalhamento completo está em [docs/context-engineering/README.md](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/docs/context-engineering/README.md).

## Regra Principal
Nenhuma capability deve receber mais contexto do que precisa, nem menos contexto do que exige.

## Fonte de Verdade
- Capabilities: [backend/agents/capabilities.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/capabilities.py)
- Contratos: [backend/agents/contracts.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/contracts.py)
- Tipos de tarefa: [backend/agents/task_types.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/task_types.py)
- Validação: [backend/agents/validators.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/validators.py)
- Clarificação: [backend/agents/clarifier.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/clarifier.py)
- Policy: [backend/agents/workflow_policy.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/workflow_policy.py)
- Replan: [backend/agents/step_replanner.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/step_replanner.py)
- Handoffs: [backend/agents/handoffs.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/handoffs.py)
- Workflow states: [backend/agents/workflow_state.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/workflow_state.py)
- Orquestração: [backend/agents/orchestrator.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/orchestrator.py)

## Invariantes
1. Não transporte dados críticos entre steps apenas como texto livre se já existir contrato estruturado.
2. Não deixe o prompt compensar um contrato ruim.
3. Não invente dados críticos para tarefas com preço, disponibilidade, filtros, datas, origem/destino, formulários ou conteúdo factual externo.
4. Clarificação deve vencer replan quando faltar informação do usuário.
5. Replan deve vencer síntese rasa quando a rota falhou mas ainda existe coleta recuperável.
6. O admin precisa continuar explicando o que aconteceu.

## Pergunta obrigatória antes de qualquer mudança
"Esta alteração melhora ou piora a qualidade do contexto entregue ao próximo step?"
