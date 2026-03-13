# File Artifact, Streaming Real e Browser Agent

## Data
2026-03-12 19:47

## Objetivo
Corrigir a renderizacao deterministica de cards de arquivos gerados, eliminar heuristica fragil de parser no frontend, trocar o falso streaming do orquestrador por `stream_openrouter` real e restaurar o Browser Agent visual no fluxo do Planner.

## Arquivos alterados
- backend/agents/orchestrator.py
- pages/ArccoChat.tsx

## O que mudou
- O orquestrador passou a emitir eventos SSE `file_artifact` sempre que detecta links de arquivo nos blocos `ANTI-LEAK`.
- O payload do evento usa `{filename, url}` para o frontend renderizar cards de preview de forma deterministica.
- As respostas finais de consolidacao e de resposta direta do supervisor deixaram de usar chunking artificial com `asyncio.sleep` e passaram a usar `stream_openrouter` real.
- O frontend ganhou estado `generatedFiles`, com limpeza por interacao e deduplicacao por URL.
- O parser de texto em `renderContent` deixou de criar `FilePreviewCard`; agora ele so converte URLs em links HTML normais.
- Os cards elegantes de arquivo agora sao renderizados apenas a partir de `generatedFiles`.
- O ramo `browser` dentro do loop do Planner voltou a emitir `browser_action` e `thought`, restaurando o card visual e a narracao estilo Manus durante navegacao headless.
- O backend em `8001` foi reiniciado manualmente para garantir carga da versao nova do orquestrador.

## Impacto
- Cards de PDF/XLSX/DOCX/PPTX gerados por link nao dependem mais da formatacao textual do LLM.
- O TTFT da resposta final melhora porque o texto final agora sai por streaming real.
- O Browser Agent volta a aparecer visualmente em prompts complexos que passam pelo Planner.
- `text_doc` continua sendo um fluxo separado para documentos inline em texto.

## Validacao
- `python3 -m py_compile` no `backend/agents/orchestrator.py`.
- `npm run build` concluido com sucesso apos a mudanca do frontend.
- Teste local do formato SSE `file_artifact` com URLs de PDF e XLSX.
- Verificacao manual de que o arquivo do orquestrador continha o patch do Browser Agent.
- Reinicio do backend local para carregar a versao nova.

## Pendencias
- Vale subir este ultimo ajuste de `file_artifact` e Browser Agent para o GitHub se ainda nao tiver sido publicado.
- Se o Browser Agent ainda nao aparecer em um prompt especifico, o proximo diagnostico e logar qual tool o Planner escolheu (`ask_browser` vs `ask_web_search`).
