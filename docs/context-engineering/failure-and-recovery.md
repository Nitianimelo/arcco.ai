# Failure And Recovery

## Objetivo
Documentar como o Arcco deve reagir quando uma etapa falha, fica ambígua ou devolve dado insuficiente.

Isso é parte de engenharia de contexto porque falha muda o contexto disponível para o próximo passo.

## Ordem de decisão
No Arcco, a ordem desejada é:
1. validar
2. classificar a falha
3. decidir clarificação se faltar input do usuário
4. decidir retry se a falha for transitória
5. decidir replan se houver capability melhor
6. só então seguir parcial

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
- policy decision
- replan
- clarificação
- parcial vs completo
