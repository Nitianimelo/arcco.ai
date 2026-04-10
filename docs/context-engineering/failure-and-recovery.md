# Failure And Recovery

## Objetivo
Documentar como o Arcco deve reagir quando uma etapa falha, fica ambígua ou devolve dado insuficiente.

Isso é parte de engenharia de contexto porque falha muda o contexto disponível para o próximo passo.

## Ordem de decisão
No Arcco, a ordem desejada é:
1. checar pré-condições
2. validar
3. classificar a falha
4. decidir clarificação se faltar input do usuário
5. decidir retry se a falha for transitória
6. decidir replan se houver capability melhor
7. só então seguir parcial

## Simplificação de governança
O núcleo de falha e recuperação foi simplificado para reduzir decisões distribuídas:
- o supervisor/orquestrador executa
- validators observam qualidade e classes de erro
- workflow policy decide a ação seguinte

Isso evita que planner, prompt, validator e replan tentem governar o mesmo problema ao mesmo tempo.

## Pré-condições
Antes de qualquer plano, o sistema precisa verificar:
- arquivos obrigatórios existem?
- arquivos obrigatórios estão `ready`?
- faltam filtros, datas ou parâmetros essenciais?
- o pedido já define o artefato final com clareza suficiente?

Se a resposta for não:
- a execução deve entrar em `awaiting_clarification`
- não deve gerar steps sobre insumos ausentes
- não deve materializar design, texto ou planilha em cima da falha

## Categorias principais de falha

### Input insuficiente
Exemplos:
- destino amplo demais
- data vaga demais
- filtro obrigatório ausente

Resposta correta:
- clarificação objetiva
- não mascarar com dado inventado

### Falha de infraestrutura
Exemplos:
- Steel indisponível
- `connect_over_cdp` falhou
- WebSocket 502

Resposta correta:
- retry/recover
- rota auxiliar de descoberta, se fizer sentido
- evitar síntese prematura

### Gate humano
Exemplos:
- captcha
- login
- cloudflare
- verificação manual

Resposta correta:
- handoff
- resume token
- pergunta objetiva

### Cobertura parcial
Exemplos:
- poucas fontes
- só parte das entidades encontradas
- sem estrutura suficiente para conferência

Resposta correta:
- pode entregar parcial
- deve explicitar gap
- pode pedir refinamento

## Princípios
1. Nunca resuma com confiança alta em cima de coleta falha.
2. Nunca tratar falha de infraestrutura como falha de conteúdo.
3. Nunca tratar captcha como erro final irreversível.
4. Replan deve preservar a intenção original.
5. Clarificação deve ter precedência sobre replan quando o problema é informação faltante do usuário.
6. Violação de contrato de ferramenta obrigatória deve falhar cedo ou entrar em recovery real, nunca virar contexto para o próximo step.
7. Erro semântico de pré-condição não pode ser marcado como sucesso técnico.

## Browser workflow
No fluxo de browser, a recuperação deve distinguir:
- infra failure
- human gate
- runtime failure
- timeout

O fallback aceitável não é sempre o mesmo.

Exemplo bom:
- `browser` falhou por infraestrutura
- `web_search` descobre fontes fortes
- `browser` volta só nas fontes selecionadas

Exemplo ruim:
- `browser` falhou
- `text_generator` resume snippets rasos como se a coleta tivesse sido completa

## Admin e logs
Toda recuperação deve deixar trilha clara:
- tipo da falha
- engine de execução
- estado das pré-condições
- policy decision
- replan
- clarificação
- parcial vs completo
