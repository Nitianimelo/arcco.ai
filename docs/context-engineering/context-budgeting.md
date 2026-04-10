# Context Budgeting

## Objetivo
Context budgeting é decidir quanto contexto cada etapa pode carregar sem perder foco, previsibilidade e custo.

Mais contexto não significa melhor contexto.

## Problema clássico
Sem budgeting, o sistema tende a:
- carregar histórico demais
- repetir fatos já normalizados
- mandar logs para o prompt
- poluir especialistas com contexto que só o orquestrador precisa

Isso gera:
- mais token
- mais latência
- menor precisão
- maior risco de alucinação

## Regra prática
Cada camada deve carregar apenas o que ela consome de fato.

### Supervisor
Pode ver:
- pedido do usuário
- contexto recente útil
- inventário de arquivos
- resultado relevante do step anterior

Não deve ver:
- todos os logs internos
- histórico bruto inteiro sem necessidade
- metadados profundos de etapas já resolvidas

### Planner
Pode ver:
- pedido do usuário
- sinais de task type
- restrições de fluxo
- capacidades disponíveis

Não deve ver:
- artefatos completos
- conteúdo bruto enorme de pesquisa
- detalhes desnecessários de steps passados

### Browser
Pode ver:
- URL
- goal
- actions hints
- filtros e parâmetros obrigatórios

Não deve ver:
- histórico longo de conversa
- resumo narrativo com informação redundante

### Text generator
Pode ver:
- factual result consolidado
- objetivo editorial
- formato esperado

Não deve ver:
- incerteza não tratada
- dados contraditórios sem validação

## Regra de redução
Ao passar contexto adiante, aplique uma destas operações:
- selecionar
- resumir
- estruturar
- descartar

Nunca passe tudo "por garantia".

## O que deve virar estado, não prompt
- stage atual
- resume token
- capability trail
- policy decision
- metadata de execução

## O que deve virar contrato, não texto solto
- entidades
- fontes
- artefatos
- falhas
- handoff de browser
- clarificações

## O que pode continuar textual
- acknowledgment ao usuário
- resumo editorial final
- pensamento curto para UX

## Regra para futuras IAs
Ao adicionar uma capability nova, responda estas perguntas:
1. Qual o menor contexto que ela precisa?
2. Qual o maior contexto que ela pode receber sem perder foco?
3. O que deve sair estruturado?
4. O que deve ser descartado ao final?
