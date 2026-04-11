# Context Layers

## Visão geral
O Arcco trabalha com camadas diferentes de contexto. Cada camada tem finalidade, formato e escopo próprios.

Misturar essas camadas é uma das formas mais rápidas de degradar qualidade, aumentar token e introduzir alucinação.

## Camada 1: Intenção do usuário
É o que o usuário pediu, no idioma e na forma em que pediu.

Exemplos:
- "pesquisa 4 barbearias e monta uma planilha"
- "resuma este PDF"
- "busque passagens para julho"

Essa camada é a origem do fluxo. Ela nunca deve ser sobrescrita silenciosamente.

## Camada 2: Contexto de tarefa
É a interpretação operacional do pedido:
- `task_type`
- complexidade
- necessidade de validação
- necessidade de clarificação
- capacidades preferidas

No código:
- [backend/agents/task_types.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/task_types.py)

## Camada 3: Contexto de planejamento
É o plano mínimo para resolver a tarefa:
- steps
- action
- capability_id
- `is_terminal`
- `needs_clarification`

No código:
- [backend/agents/planner.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/planner.py)
- [backend/agents/contracts.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/contracts.py)

## Camada 4: Contexto de execução de step
É o contexto estritamente necessário para uma capability rodar.

Exemplos:
- `query` para `web_search`
- `url`, `goal`, `actions` para `browser`
- `code` para `python`
- `instructions`, `content_brief` para `text_generator`

Essa camada deve ser pequena, objetiva e auditável.

## Camada 5: Contexto factual intermediário
É o resultado factual que precisa ser preservado entre steps.

Exemplos:
- entidades encontradas na busca
- fontes e URLs confiáveis
- artefatos gerados
- snippets relevantes
- resultado normalizado de uma coleta

Essa camada deve preferir contrato estruturado.

## Camada 5.1: Document Workspace
Para documentos anexados, o Arcco não deve despejar texto bruto ou imagens no prompt principal.

Em vez disso, a ingestão do documento gera um workspace operacional por sessão, com:
- texto extraído
- chunks prontos para RAG lexical
- imagens extraídas e salvas
- metadados como `text_char_count`, `image_count` e `chunk_count`

O agente deve receber apenas o inventário desse workspace e consultar o conteúdo sob demanda.

Isso reduz consumo de tokens, evita "lost in the middle" e separa ingestão de transformação.

No código:
- [backend/agents/handoffs.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/handoffs.py)
- [backend/agents/contracts.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/contracts.py)

## Camada 6: Contexto de controle
É o contexto que governa a execução:
- validações
- clarificações
- policy decision
- retry
- replan
- workflow state

Essa camada não é o conteúdo final; ela é o mecanismo que decide o próximo passo.

## Camada 7: Contexto de observabilidade
É o que permite a humanos e IAs entenderem o que aconteceu depois:
- logs
- admin execution view
- workflow snapshots
- capability results
- policy trail
- clarification trail

Sem essa camada, o sistema pode até funcionar, mas se torna difícil de manter.

## Regra de separação
Cada camada deve responder a uma pergunta diferente:
- intenção: o que o usuário quer?
- tarefa: que tipo de problema é esse?
- plano: quais steps faremos?
- step: o que esta capability precisa agora?
- factual intermediário: o que o próximo step precisa herdar?
- controle: devemos seguir, perguntar, tentar de novo ou trocar rota?
- observabilidade: como explicamos isso depois?
