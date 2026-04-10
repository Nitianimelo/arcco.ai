# Examples

## Exemplo 1: Busca simples factual
Pedido:
"quem é o CEO da empresa X hoje?"

Fluxo esperado:
1. task type simples
2. `web_search`
3. resposta direta

Contexto:
- não precisa browser
- não precisa planner pesado
- não precisa handoff

## Exemplo 2: Busca + planilha
Pedido:
"pesquise 4 barbearias e monte uma planilha"

Fluxo esperado:
1. `web_search`
2. normalização das entidades
3. validação
4. `python`

Contexto crítico:
- nomes das entidades
- fontes
- campos mínimos

Erro a evitar:
- `python` inventar ou trocar entidades

## Exemplo 3: Passagens com filtros
Pedido:
"busca passagens de Fortaleza para São Paulo em julho, ida e volta, 1 adulto, econômica"

Fluxo esperado:
1. `task_type = browser_workflow`
2. `web_search` para encontrar fontes fortes
3. `browser` para preencher filtros reais
4. validação
5. resposta ou artefato

Se houver captcha:
1. `browser` entra em handoff
2. usuário resolve
3. `resume_token`
4. fluxo continua

Erro a evitar:
- resumir snippets rasos como se fosse coleta final

## Exemplo 4: Documento massivo
Pedido:
"analise estes 30 PDFs e me diga os principais riscos"

Fluxo esperado:
1. ingestão
2. OCR
3. index
4. clarificação do objetivo
5. retrieval seletivo
6. `text_generator`
7. cleanup

Contexto crítico:
- não carregar todos os PDFs crus no prompt final
- manter estado de pipeline
- preservar só o que importa para a resposta
