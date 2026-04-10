# Browser Context

## Objetivo
Explicar como o browser workflow deve receber contexto, executar, pedir handoff e devolver contexto útil.

## Papel do browser
O `browser` existe para tarefas que dependem de:
- JavaScript real
- interação
- preenchimento de inputs
- seleção de datas
- filtros
- formulários
- login
- captcha
- coleta visual de dados que a busca textual não resolve

## O que o browser deve receber
Contexto mínimo:
- `url`
- `goal`

Contexto opcional:
- `actions`
- `wait_for`
- `mobile`
- `include_tags`
- `exclude_tags`
- `resume_token`

## O que o browser não deve receber
- histórico completo da conversa
- resumo enorme de passos anteriores
- logs operacionais inteiros

## Estratégia recomendada
Para tarefas interativas como passagens e hotéis:
1. `web_search` descobre fontes fortes
2. `browser` acessa a fonte escolhida
3. preenche origem, destino, datas e filtros
4. coleta o resultado final
5. se houver gate humano, entra em handoff

Não começar cegamente com `browser` quando ainda não há fonte definida é mais caro e menos resiliente.

## Handoff humano
O browser já suporta:
- captcha
- verificação humana
- bloqueio visual
- retomada com `resume_token`

Esses casos não são erro final.

## Resultado esperado do browser
O browser deve devolver um `CapabilityResult` que permita:
- validação
- síntese
- log
- admin trail

Idealmente com:
- conteúdo útil
- URLs relevantes
- estado do workflow
- `handoff_required` ou `error_text` quando aplicável

## Falhas do browser

### Infra failure
Exemplos:
- Steel/CDP indisponível
- 502
- falha de websocket

Ação esperada:
- retry curto
- recuperação estrutural
- evitar cair direto em síntese rasa

### Human gate
Exemplos:
- captcha
- cloudflare
- login

Ação esperada:
- handoff
- pergunta objetiva
- manter sessão viva para resume

### Runtime failure
Exemplos:
- seletor ruim
- página mudou
- timeout parcial

Ação esperada:
- reavaliar rota
- talvez replan
- talvez descoberta de fonte antes de nova tentativa

## Observabilidade
O chat e o admin devem refletir:
- navegador iniciando
- navegador agindo
- aguardando usuário
- retomado
- concluído
- erro
- replan

Sem isso, o usuário vê só “falhou” e a futura IA não entende o motivo.
