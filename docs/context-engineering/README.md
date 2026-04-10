# Context Engineering

## Objetivo
Esta pasta documenta como o Arcco constrói, reduz, preserva e transfere contexto ao longo da execução.

Ela existe por três motivos:
- reduzir alucinação entre steps
- tornar o backend legível para futuras IAs e desenvolvedores
- transformar decisões de contexto em arquitetura explícita, não em comportamento implícito

No Arcco, contexto não é só "prompt". Contexto inclui:
- intenção do usuário
- parâmetros explícitos e implícitos
- estado da execução
- outputs intermediários
- handoffs estruturados
- validações
- clarificações
- fallback e replan
- logs e observabilidade

## Leitura recomendada
1. [context-layers.md](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/docs/context-engineering/context-layers.md)
2. [context-contracts.md](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/docs/context-engineering/context-contracts.md)
3. [context-budgeting.md](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/docs/context-engineering/context-budgeting.md)
4. [failure-and-recovery.md](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/docs/context-engineering/failure-and-recovery.md)
5. [browser-context.md](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/docs/context-engineering/browser-context.md)
6. [examples.md](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/docs/context-engineering/examples.md)

## Regras centrais
1. Toda capability deve receber um contexto mínimo suficiente, não um contexto máximo possível.
2. Contexto factual deve preferir contratos estruturados a resumos narrativos.
3. O planner decide sequência; o dispatcher executa; validators conferem; policy decide a continuação; replan troca a rota quando necessário.
4. Clarificação existe para reduzir inferência arriscada, não para travar o usuário desnecessariamente.
5. O sistema pode entregar parcial, mas não deve mascarar incerteza.
6. Logs e painel admin fazem parte da engenharia de contexto, porque são a trilha auditável da execução.

## Onde isso aparece no código
- Capabilities: [backend/agents/capabilities.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/capabilities.py)
- Contracts: [backend/agents/contracts.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/contracts.py)
- Task typing: [backend/agents/task_types.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/task_types.py)
- Validators: [backend/agents/validators.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/validators.py)
- Clarifier: [backend/agents/clarifier.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/clarifier.py)
- Policy: [backend/agents/workflow_policy.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/workflow_policy.py)
- Replan: [backend/agents/step_replanner.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/step_replanner.py)
- Handoffs: [backend/agents/handoffs.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/handoffs.py)
- Workflow state: [backend/agents/workflow_state.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/workflow_state.py)
- Orquestrador: [backend/agents/orchestrator.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/orchestrator.py)
- Painel admin / chat runtime: [pages/AdminPage.tsx](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/pages/AdminPage.tsx) e [pages/ArccoChat.tsx](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/pages/ArccoChat.tsx)

## Quando alterar esta pasta
Atualize esta pasta sempre que houver mudança em pelo menos um dos pontos abaixo:
- planner
- contracts
- handoffs
- validators
- clarifier
- workflow policy
- step replan
- browser workflow
- task typing
- admin observability

## Anti-padrões
- Colocar toda a semântica do sistema em prompt.
- Passar um resumo narrativo como única fonte factual para o step seguinte.
- Misturar estado de runtime com memória de usuário.
- Fazer fallback automático para saída bonita quando a coleta factual falhou.
- Adicionar exceções no orquestrador sem documentar a nova regra de contexto.
