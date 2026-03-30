# CHANGELOG — Registro de Modificações por IA

> Toda IA que modificar código neste repositório DEVE registrar aqui.
> Formato: data/hora, arquivos modificados, o que foi feito, por quê.

## 2026-03-30 (11) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/services/pricing_service.py` (NOVO)
- `backend/core/llm.py`
- `backend/services/execution_log_service.py`
- `backend/api/chat.py`
- `backend/api/admin.py`
- `pages/AdminPage.tsx`

### O que foi feito:
1. **pricing_service.py** (NOVO) — Serviço de preços via OpenRouter `/api/v1/models` com cache de 1h. Funções `get_model_prices(model_id)` e `estimate_cost(model_id, prompt_tokens, completion_tokens)`. Fallback de $1.00/$3.00/1M para modelos desconhecidos.
2. **llm.py** — Adicionado `ContextVar[dict]` para acumulação de tokens por request assíncrona (isolado). Funções `start_token_tracking()` e `get_token_usage()`. `call_openrouter` acumula `usage` no ContextVar. `stream_openrouter` recebe `stream_options: {include_usage: true}` e captura tokens do chunk final (set, não +=).
3. **execution_log_service.py** — `create_execution()` aceita `model_used`. `finish_execution()` aceita `total_tokens` e `total_cost_usd`. `finish_agent()` aceita `prompt_tokens`, `completion_tokens`, `total_tokens`, `estimated_cost_usd`. Todos persistem no Supabase.
4. **chat.py** — Importa `start_token_tracking/get_token_usage` e `estimate_cost`. Inicia tracking no começo de `generate()`. No `finally`, lê usage (prioriza `stream_*`), calcula custo e passa para `finish_agent()` e `finish_execution()`. `_save_conversation_and_update_memory` salva tokens na mensagem do assistant.
5. **admin.py** — 4 novos endpoints: `GET /api/admin/token-usage/summary?days=N` (totais + by_mode + by_model + by_day + by_user), `GET /api/admin/token-usage/executions?days=N&mode=X&limit=N` (lista execuções com tokens/custo). Aggregação feita em Python (PostgREST não suporta GROUP BY).
6. **AdminPage.tsx** — Aba "Custos" completa: 4 cards (Total Tokens, Custo Total, Execuções, Custo Médio), breakdown por modo (chat vs agente com barra de progresso), Top Modelos, Consumo por Dia, Top Usuários, tabela de execuções recentes. Filtros de período (7/30/90/365d) e modo (Todos/Normal/Agente).

### Por quê:
Implementação completa de rastreamento de tokens e custos por chamada LLM. Permite ao admin monitorar gastos por modelo, usuário e período, com controle granular para precificação e gestão de custos da plataforma.

## 2026-03-29 (10) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **ArccoChat.tsx** — Removido badge/card de clima (Fortaleza 27°C) do greeting state.
2. **ArccoChat.tsx** — `getWeatherSubtitle` reescrita com ~35 frases criativas e action-oriented que mencionam cidade, temperatura e horário. Ex: "Dia de sol aí em Fortaleza? O que vamos criar hoje?", "Chovendo em São Paulo com 18°. Que projeto tiramos do papel?".
3. **ArccoChat.tsx** — `getSubtitle` (fallback sem localização) reescrita com ~20 frases por período (madrugada/manhã/tarde/noite) com chamada para ação.

### Por quê:
Saudação estava genérica e sem personalidade. Agora usa os dados de clima/localização já coletados de forma criativa no texto, sem exibir card separado.

## 2026-03-29 (9) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/agents/executor.py`

### O que foi feito:
1. **executor.py** — Removido bloco `except` duplicado e inválido no final de `_analyze_web_pages`. O segundo `except` referenciava `action` (variável inexistente), causando erro de sintaxe Python.
2. **executor.py** — Auto-healing: modelo trocado de `openai/gpt-4o-mini` para `google/gemini-2.5-flash`, eliminando dependência de saldo OpenAI.

### Por quê:
Dois bugs fatais: erro de sintaxe que impedia o módulo de carregar, e dependência de créditos OpenAI no auto-healing.

## 2026-03-29 (8) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/agents/orchestrator.py`

### O que foi feito:
1. **orchestrator.py** — Fix do bug de clarificação: quando o usuário responde a uma pergunta de clarificação, o planner recebia apenas a última mensagem (ex: "10 slides sobre marketing") sem contexto do pedido original. Agora, em conversas multi-turno (`_user_msgs_count > 1`), o orchestrator constrói `_planner_intent` com as últimas 8 mensagens formatadas como `[Usuário]/[Assistente]`, dando ao planner contexto completo para gerar o plano correto. `user_intent` original é preservado para filtro de skills.

### Por quê:
O pipeline quebrava após o usuário responder perguntas de clarificação porque o planner via a resposta isolada e não conseguia gerar um plano coerente.

## 2026-03-29 (7) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/core/config.py`
- `backend/api/admin.py`
- `pages/AdminPage.tsx`

### O que foi feito:
1. **config.py** — Adicionados campos `admin_username` (default: "nitiani") e `admin_password` (default: "96947188") ao `AgentConfig`, lidos de env vars `ADMIN_USERNAME` / `ADMIN_PASSWORD`.
2. **admin.py** — Implementado sistema de autenticação do painel admin:
   - `POST /api/admin/login` (rota pública) — valida credenciais com `secrets.compare_digest`, retorna token SHA256 determinístico `sha256(user:pass:arcco_admin)`.
   - Função `verify_admin` como FastAPI Dependency — valida Bearer token em todas as rotas protegidas.
   - `Depends(verify_admin)` aplicado a todas as 12 rotas existentes.
3. **AdminPage.tsx** — Tela de login adicionada antes do painel:
   - Estado `adminToken` persistido em `localStorage`.
   - Formulário de login com usuário/senha, mensagem de erro, botão com loading.
   - Helper `adminFetch` injeta `Authorization: Bearer {token}` em todas as 10 chamadas ao backend; auto-logout em resposta 401.
   - Botão "Sair" adicionado ao header do painel.

### Por quê:
Painel admin estava totalmente sem autenticação — qualquer pessoa com a URL acessava e podia modificar prompts, modelos e tools de todos os agentes. Credenciais ficam apenas no backend (config.py / env vars), nunca expostas ao frontend.

## 2026-03-29 (6) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `nginx/nginx.conf`

### O que foi feito:
1. **nginx.conf** — Blocos `location /api/agent/` (HTTP porta 80 e HTTPS porta 443): timeout aumentado de 120s para 300s e adicionado `proxy_connect_timeout 300s`. Admin mantido em 60s (não executa tarefas longas).

### Por quê:
A ferramenta `deep_research` pode levar até 180 segundos. O Nginx com timeout padrão/anterior (120s) cortava a conexão com 504 antes do agente terminar. Com 300s (5 minutos), o Nginx aguenta qualquer tarefa de agente incluindo deep_research + browser sessions longas.

## 2026-03-29 (5) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/agents/tools.py`

### O que foi feito:
1. **tools.py** — Description do `ask_text_generator` em `SUPERVISOR_TOOLS` atualizada: removido "documento bruto em texto", substituído por "documento oficial (Contratos, Relatórios, Artigos, Propostas, Manuais) formatado em Markdown rico (títulos #, listas e negrito) para exportação perfeita em PDF/DOCX".

### Por quê:
Contradição entre tools.py e prompts.py: o TEXT_GENERATOR_SYSTEM_PROMPT foi atualizado para usar Markdown rico, mas a description da tool ainda dizia "texto bruto", causando conflito no momento em que o LLM lê a definição da ferramenta e decide como populá-la.

## 2026-03-29 (4) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/agents/prompts.py`

### O que foi feito:
1. **prompts.py** — `PLANNER_SYSTEM_PROMPT`: FERRAMENTAS BASE e REGRAS DE DECISÃO substituídos pela Matriz de Decisão Definitiva:
   - FERRAMENTAS BASE: critérios claros para `text_generator` (leitura longa) vs `design_generator` (impacto visual). `python` especifica geração Excel/CSV. `browser` mantém instrução stateless + passo único.
   - Nova regra explícita para sequências visuais (carrossel, slides, pitch deck): SEMPRE `slide_generator` → `design_generator`, nunca pular o roteiro.
   - REGRAS DE DECISÃO reestruturadas em 5 grupos: Sequências Visuais, Texto vs. Design, Relatórios e Dados, Automação Web, Otimização.
   - Regra `multi_doc_investigator` preservada. Nota "skill não listada → NÃO use" consolidada no bloco Skills.

### Por quê:
Três inconsistências de roteamento: (1) carrosséis iam direto para design_generator sem slide_generator; (2) fronteira texto/design era ambígua; (3) ausência de critério claro para dados vs. narrativa.

---

## 2026-03-29 (3) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/agents/prompts.py`
- `backend/agents/planner.py`

### O que foi feito:
1. **prompts.py** — Regra 4 do `CHAT_SYSTEM_PROMPT` reescrita: remove instrução "SEM ferramenta — resposta direta" que conflitava com o Planner. Agora instrui o Supervisor a SEMPRE delegar documentos longos (>3 parágrafos) para `ask_text_generator`, reservando resposta direta apenas para textos curtos (1-2 parágrafos).
2. **prompts.py** — `TEXT_GENERATOR_SYSTEM_PROMPT`: substituída a linha "NUNCA COLOQUE # ou *" por instrução oposta — USE formatação Markdown rica (títulos #, listas -, negrito **) para gerar documentos profissionais exportáveis.
3. **planner.py** — `import re` adicionado. Parsing frágil `if raw_content.startswith("```")` substituído por `re.search(r'\{.*\}', raw_content, re.DOTALL)` — extrai o JSON independentemente de texto introdutório ou blocos markdown que o LLM inclua na resposta.

### Por quê:
Três fragilidades em produção: (1) conflito de roteamento Supervisor vs Planner para textos longos, (2) documentos exportados sem formatação por restrição incorreta de Markdown, (3) Planner falhando silenciosamente quando o LLM adicionava texto antes do JSON.

---

## 2026-03-29 (2) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/agents/prompts.py`
- `backend/agents/tools.py`

### O que foi feito:
1. **prompts.py** — Regra 2 do `CHAT_SYSTEM_PROMPT` (`ask_browser`) expandida com dois sub-itens:
   - REGRA DE AUTONOMIA: instrui o Supervisor a inferir e incluir todas as ações de browser (click, scroll, write, scrape) em uma única chamada, sem pedir confirmação ao usuário.
   - SELETORES INTELIGENTES: ensina o Supervisor a usar seletores de texto Playwright (`text="Aceitar"`) como alternativa mais robusta quando o CSS selector não for óbvio.
2. **prompts.py** — Linha `browser` do `PLANNER_SYSTEM_PROMPT` atualizada: instrui o Planner a agrupar todo o objetivo de navegação em UM ÚNICO passo com todas as actions, nunca criar passos separados para cada ação individual de browser.
3. **tools.py** — Campo `selector` nos items do array `actions` da tool `ask_browser` atualizado: descrição agora menciona seletores de texto Playwright (`text="..."`) além de CSS, com exemplos práticos.

### Por quê:
Melhorar a autonomia do Browser Agent — o Supervisor passou a inferir ações de browser sozinho (scroll, click, cookie banners), o Planner agrupa toda a navegação em 1 passo eficiente, e o LLM sabe que pode usar seletores robustos baseados em texto visível.

---

## 2026-03-29 — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **ArccoChat.tsx** — Redesign das funções de saudação (`getWeatherSubtitle` e `getSubtitle`):
   - Removido o horário literal "Você chegou às HH:MM" (substituído por contexto qualitativo).
   - Adicionado helper `_pick(arr)` com seed determinístico (`hora * 7 + dia * 31 + mês * 13`) — seleciona variante diferente a cada hora/dia sem flickar durante a sessão.
   - `getWeatherSubtitle`: cada condição agora tem um pool de 3–5 variantes. Ex: chuva → ["Chuva de tarde em SP.", "Tá chovendo em SP.", "SP molhada essa tarde.", ...]. Inclui combinações de clima + temperatura + parte do dia + fim de semana.
   - `getSubtitle` (fallback sem clima): pool de variantes por faixa horária + dia da semana (segunda, sexta, domingo, madrugada, etc.).
   - Frases são curtas e naturais — a IA demonstra saber onde o usuário está e o momento sem explicitar o relógio.

### Por quê:
Usuário não queria o horário exato. Queria que a IA demonstrasse awareness contextual (parte do dia, clima, fim de semana, madrugada) de forma fluida e variada, misturando diferentes sinais a cada sessão.

---

## 2026-03-28 (2) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **ArccoChat.tsx** — Redesign completo do Activity Panel (painel de steps do agente):
   - Removido o card/wrapper com borda e fundo escuro — o painel agora flutua livremente no chat, sem caixa.
   - Tipografia Inter (sans-serif) em `text-sm`, substituindo a aparência de "terminal".
   - Steps ativos: efeito `shimmer-text` (gradiente animado indigo/violet sobre o texto) — elegante e discreto.
   - Steps concluídos: texto em `text-neutral-700` com ✓ verde suave + animação `animate-check-pop`.
   - Steps pending: ponto central cinza.
   - Thoughts (raciocínio interno): texto italic, indentado, `text-xs`, muito discreto.
   - Pre-action message: linha com spinner circular fino (`border-t-transparent animate-spin`) e `text-neutral-500`.
   - Estado loading (sem steps): logo Arcco em `animate-pulse-soft` + "Analisando..." bem suave.
   - Estado collapsed: seta SVG + "N etapas · Xs" em `text-neutral-700`, muito discreto.
   - Botão "Recolher" quando concluído: seta SVG up + contador de tempo, linha única.
   - Ícone de estado running: dot `w-[5px]` com `animate-ring-pulse` (glow sutil).
   - Non-agent thinking: dot `bg-indigo-400/60 animate-pulse` + texto `text-neutral-500`.

### Por quê:
Redesign pedido pelo usuário. O painel anterior tinha visual de "terminal" (card escuro com borda, fonte pequena, layout denso). Novo design é solto no chat, fonte maior, animações elegantes, inspirado em Claude Code e interfaces de IAs agênticas modernas.

---

## 2026-03-28 — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/AdminPage.tsx`

### O que foi feito:
1. **AdminPage.tsx** — Corrigido botão "Copiar logs consolidados" que falhava silenciosamente em HTTP:
   - `copyExecutionLogs()`: adicionado try/catch em torno de `navigator.clipboard.writeText()` com fallback via `document.execCommand('copy')` usando textarea temporário oculto (funciona em HTTP/não-HTTPS).
   - Adicionada função `downloadExecutionLogs()` que baixa os logs como arquivo `.json` diretamente (não depende de Clipboard API nem HTTPS).
   - Adicionado estado `downloadedExecutionId` para feedback visual do botão download.
   - Adicionado import de `Download` de `lucide-react`.
   - Na UI: botão "Copiar" agora fica ao lado de novo botão "Baixar .json" (verde) — alternativa robusta quando copy falha.

### Por quê:
`navigator.clipboard.writeText()` exige "secure context" (HTTPS ou localhost). O site está temporariamente em HTTP enquanto SSL não é renovado. O botão copy não funcionava e o usuário não conseguia extrair logs para debugar erros no fluxo dos agentes.

---

## 2026-03-27 22:00 — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `nginx/nginx.conf`

### O que foi feito:
1. **nginx.conf** — Bloco HTTP agora serve o site completo (API + frontend) sem redirect pro HTTPS. Site funciona via HTTP quando não há certificado SSL real.

### Por quê:
Rate limit do Let's Encrypt atingido. Site precisa funcionar via HTTP até 29/03.

---

## 2026-03-27 — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **ArccoChat.tsx** — Redesign completo do painel de pensamento/steps do agente:
   - Removido o indicador "Trabalhando" de dentro do balão da mensagem do assistente
   - Balão vazio do assistente agora é escondido enquanto o agente está processando (evita bolha vazia no topo)
   - Criado painel unificado "Activity Panel" que fica abaixo das mensagens (perto do input), combinando: thinking indicator + steps + loading state
   - Agent mode: painel com borda arredondada, header com status (Processando/Concluído) e timer, steps com ícones (✓ done, ● running, · pending), thoughts indentados com borda lateral, mensagem pre_action com spinner na base do painel, botão "Recolher" quando concluído, modo collapsed compacto com seta
   - Non-agent mode: indicador simples com dot pulsante e mensagem de thinking
   - Melhor espaçamento (space-y-3), tipografia mais limpa (text-xs, tracking), cores mais sutis (emerald para done, indigo para running)

2. **ArccoChat.tsx (chunk handler)** — No modo agente, `chatThinkingVisible` agora NÃO é desligado quando o primeiro chunk chega. As mensagens de `pre_action` ("vou abrir o browser...") persistem no painel durante toda a execução dos steps. No chat mode (não-agente), comportamento mantido (esconde após 800ms).

### Por quê:
O painel de pensamento aparecia no topo (dentro do balão da mensagem), longe do input. Usuário pediu para ficar mais perto do input e mais profissional. Agora fica abaixo de todas as mensagens, com visual clean. As mensagens de pre_action ficam visíveis durante toda a execução.

## 2026-03-27 12:00 — Claude Code (claude-sonnet-4-6) — Frontend responsivo para mobile

### Arquivos modificados:
- `App.tsx`
- `components/Sidebar.tsx`
- `pages/ArccoChat.tsx`
- `pages/AdminPage.tsx`
- `components/SettingsModal.tsx`

### O que foi feito:
1. **App.tsx** — Adicionado estado `isMobile` (detecta <768px) e `isMobileSidebarOpen`. Botao hamburger (Menu icon) fixo no canto superior esquerdo, visivel apenas no mobile. Margem do main condicional (ml-0 no mobile). Novas props `isMobile`, `isMobileOpen`, `onMobileClose` passadas ao Sidebar.

2. **Sidebar.tsx** — Convertido para drawer mobile: overlay escuro (bg-black/60 backdrop-blur), sidebar desliza com translate-x (slide in/out). `effectiveCollapsed` ignora estado collapsed no mobile (sempre expandido). Wrappers `handleNavigateWithClose`, `handleLoadSessionWithClose`, `handleSelectProjectWithClose` fecham o drawer ao navegar. Botoes collapse/expand escondidos no mobile.

3. **ArccoChat.tsx** — Header: h-14 no mobile (h-16 desktop), pl-14 para dar espaco ao hamburger. Mensagens: max-w-[95%] no mobile (85% sm, 80% md). Avatar: w-8 h-8 no mobile (50px desktop). Steps indentation: pl-0 no mobile. Input area: px-3/px-2 no mobile. Bottom bar: p-3 no mobile.

4. **AdminPage.tsx** — Grid de cards: grid-cols-1 mobile, sm:2, lg:3. Tabs: overflow-x-auto scrollavel, labels hidden no mobile (so icones). Paddings: px-4 mobile, px-6 desktop.

5. **SettingsModal.tsx** — Largura: w-full max-w-[90vw] no mobile, w-[860px] no desktop. Margem m-4 no mobile.

### Por que:
O frontend era desktop-first sem suporte mobile. Sidebar ocupava espaco fixo, nao havia hamburger menu, paddings eram grandes demais para telas pequenas, e modais tinham largura fixa que transbordava.

---

## 2026-03-27 10:00 — Claude Code (claude-sonnet-4-6) — Fix definitivo SSL: entrypoint self-signed bootstrap

### Arquivos modificados:
- `nginx/entrypoint.sh` (NOVO)
- `Dockerfile.frontend`

### O que foi feito:
1. **entrypoint.sh** — Script que roda antes do Nginx iniciar. Checa se `/etc/letsencrypt/live/app.arccoai.com/fullchain.pem` existe. Se sim, inicia Nginx direto. Se nao, gera certificado self-signed temporario com openssl (RSA 2048, validade 1 dia) no mesmo path que o nginx.conf espera, e inicia Nginx. Isso quebra o chicken-and-egg: Nginx sobe na porta 80 + 443 (com cert fake), Certbot valida via porta 80 e gera cert real, restart do Nginx pega o cert verdadeiro.

2. **Dockerfile.frontend** — Stage 2 agora instala `openssl` via apk, copia `entrypoint.sh`, da chmod +x, e usa ENTRYPOINT em vez de CMD.

### Por que:
Nginx crashava em loop porque o bloco `listen 443 ssl` referenciava certificados que nao existiam. Certbot precisava do Nginx rodando na porta 80 para validar o dominio. Sem o entrypoint, era impossivel gerar os certificados na primeira execucao. Com o self-signed temporario, ambos os servicos conseguem completar seu papel.

---

## 2026-03-27 08:30 — Claude Code (claude-sonnet-4-6) — Fix deploy Hostinger: Certbot + HTTP temporario

### Arquivos modificados:
- `docker-compose.yml`
- `nginx/nginx.conf`

### O que foi feito:
1. **docker-compose.yml** — Substituido volume host-mounted (`/docker/arccoai/certbot/conf`) por Docker volumes persistentes (`certbot-etc`, `certbot-var`). Adicionado servico `certbot` (certbot/certbot:latest) que executa `certonly --webroot` para gerar certificados SSL automaticamente via ACME challenge.

2. **nginx/nginx.conf** — Bloco HTTPS (443 ssl) comentado temporariamente. Servidor HTTP (80) agora serve a aplicacao completa (API, admin, health, frontend). Adicionado `location /.well-known/acme-challenge/` para validacao do Certbot. Removido redirect 301 HTTP→HTTPS. Removido `text/html` duplicado do gzip_types (fix warning). Removido `http2` do listen (deprecated em nginx recente).

### Por que:
Nginx crashava em loop no Hostinger porque os certificados SSL nao existiam no path `/etc/letsencrypt/live/app.arccoai.com/`. O pipeline de deploy da Hostinger apaga arquivos locais, entao volumes host-mounted nao persistem. Com Docker volumes + Certbot como servico, os certificados sao gerados automaticamente e persistem entre deploys. Apos Certbot gerar os certs, basta descomentar o bloco HTTPS e fazer novo push.

---

## 2026-03-27 06:00 — Claude Code (claude-sonnet-4-6) — Atualização de prompts: Supervisor, Planner, QA

### Arquivos modificados:
- `backend/agents/prompts.py`

### O que foi feito:

1. **CHAT_SYSTEM_PROMPT (Supervisor)** — Adicionada regra 11 "SKILLS DINÂMICAS DE NEGÓCIO". Instrui o Supervisor a preferir skills especializadas sobre ferramentas genéricas quando disponíveis (ex: web_form_operator em vez de ask_browser para formulários, local_lead_extractor em vez de ask_web_search para leads, multi_doc_investigator em vez de read_session_file repetido, slide_generator antes de design_generator para apresentações).

2. **PLANNER_SYSTEM_PROMPT** — Reescrito com mais contexto. Cada ferramenta agora tem descrição de quando usar e quando NÃO usar. Adicionado bloco "REGRAS DE DECISÃO" com 7 regras que priorizam skills sobre ferramentas genéricas. Explica que skills são injetadas dinamicamente e que o planner deve usar o skill_id como action. Adicionada regra de minimizar passos.

3. **QA_SYSTEM_PROMPT** — Adicionado critério de validação para skills dinâmicas: aprovar se saída contém dados úteis (tabela, resumo, CSV, dossiê); reprovar apenas se saída é erro genérico ou skill não executou por falta de parâmetro. Critério de design atualizado para aceitar HTML além de JSON com slides.

### Por quê:
Os prompts originais não mencionavam skills dinâmicas. Sem essa orientação, o Supervisor tentaria resolver com ferramentas genéricas (ex: chamar ask_web_search 5 vezes em vez de local_lead_extractor), o Planner não saberia quando escolher uma skill, e o QA não saberia como validar saídas de skills.

---

## 2026-03-27 05:00 — Claude Code (claude-sonnet-4-6) — Skill Multi-Document Investigator

### Arquivos modificados:
- `backend/skills/multi_doc_investigator.py` (NOVO)

### O que foi feito:
1. **multi_doc_investigator.py** — Nova skill que cruza informacoes de todos os documentos de uma sessao. Fluxo: lista arquivos da sessao via `session_file_service` → para cada arquivo `ready`, le o texto extraido e busca chunks relevantes via `ephemeral_rag_service.search_relevant_chunks` (top 5 por arquivo, max 30 total) → envia chunks com nomes de fonte ao LLM (gpt-4o-mini) com prompt de "Investigador Forense" que obriga citacao de fontes → retorna dossie + rodape com arquivos consultados. Limita contexto a 25k chars. Trata arquivos em processamento e ausentes. Keywords: documentos, comparar, cruzar, investigar, dossie, contrato, consolidar.

### Por que:
Feature de alto valor para clientes que fazem upload de dezenas de documentos e querem respostas complexas cruzando informacoes entre eles (ex: "qual o valor total de todos os contratos?"). Usa infraestrutura existente (RAG lexical + session files) sem dependencias novas. GC automatico via session_gc_service.

---

## 2026-03-27 04:30 — Claude Code (claude-sonnet-4-6) — Planner reconhece skills dinamicas

### Arquivos modificados:
- `backend/agents/prompts.py`
- `backend/agents/orchestrator.py`

### O que foi feito:
1. **prompts.py** — Adicionado paragrafo no `PLANNER_SYSTEM_PROMPT` explicando que skills dinamicas podem ser usadas como `action` no plano (ex: `action="local_lead_extractor"`).

2. **orchestrator.py** — No `_PLANNER_ACTION_TO_TOOL` mapping, adicionado fallback: se a action nao esta no mapa fixo mas e um skill_id valido (`skills_loader.is_skill(step.action)`), usa o skill_id diretamente como `_forced_tool_name`. Isso garante `tool_choice` forcado para a skill correta.

### Por que:
Sem esse fix, o planner so conhecia 8 actions fixas. Skills novas (web_form_operator, local_lead_extractor) so funcionariam no loop ReAct (nao-deterministico). Com o fix, o planner pode gerar `action="local_lead_extractor"` e o orchestrator forca a tool correta via `tool_choice`, garantindo execucao deterministica.

---

## 2026-03-27 04:00 — Claude Code (claude-sonnet-4-6) — 3 features: RPA, Lead Extractor, Auto-Healing

### Arquivos modificados:
- `backend/skills/web_form_operator.py` (NOVO)
- `backend/skills/lead_extractor.py` (NOVO)
- `backend/agents/executor.py`

### O que foi feito:

1. **web_form_operator.py** — Nova skill de RPA. Recebe URL + dados, navega via browser_service, extrai HTML dos formularios, LLM mapeia campos para acoes (write/click), executa no Browserbase. Keywords: formulario, preencher, cadastrar, crm.

2. **lead_extractor.py** — Nova skill de extracao de leads. Recebe nicho + localizacao + plataforma (web/google_maps/instagram). Gera script Python com DuckDuckGo Search, executa no E2B sandbox, parseia resultados e retorna tabela Markdown + upload CSV ao Supabase. Keywords: lead, prospectar, buscar empresas, b2b, sdr.

3. **executor.py** — Implementado loop de auto-healing no `_execute_python`. Se codigo falha, extrai erro e chama gpt-4o-mini para reescrever o codigo corrigido. Reexecuta ate 2x adicionais (3 tentativas total). Invisivel para o orchestrator e frontend — so loga no terminal. Remove markdown da resposta do LLM se necessario. Se todas as tentativas falham, retorna ultimo erro formatado.

### Por que:
- RPA: permite ao usuario pedir "cadastra o Joao Silva no CRM" e a IA executa autonomamente.
- Leads: funcionalidade de prospecao B2B — usuario pede leads e recebe CSV pronto para trabalhar.
- Auto-Healing: estabilidade critica — se LLM esquece um import ou gera syntax error, a propria ferramenta corrige sem engasgar a plataforma.

---

## 2026-03-27 03:00 — Claude Code (claude-sonnet-4-6) — Fix slides preto/branco no export

### Arquivos modificados:
- `backend/services/file_service.py`

### O que foi feito:
1. **file_service.py** — Criado `_SHOW_SLIDE_JS`, um helper JS robusto para isolar slides antes do screenshot. Além de `display` e `opacity`, agora força `visibility: visible`, `position: relative`, `transform: none`, `min-height: 100vh`, `width: 100%`, adiciona classe `active` e força reflow via `document.body.offsetHeight`. Timeout aumentado de 300ms para 600ms. Aplicado nas 3 funções: `generate_pdf_playwright`, `html_to_screenshot`, `html_to_pptx`.

### Por quê:
Bug: slides após o primeiro eram exportados como imagem preta ou branca. O JS anterior só mudava `display` e `opacity`, insuficiente quando o CSS da apresentação usa `position: absolute`, `transform`, transitions ou backgrounds dependentes de classes. O slide ficava "visível" mas sem dimensão real no viewport.

---

## 2026-03-27 02:30 — Claude Code (claude-sonnet-4-6) — Export dialog com opções de slide, tamanho e resolução

### Arquivos modificados:
- `backend/api/export.py`
- `backend/services/file_service.py`
- `components/chat/DesignPreviewModal.tsx`

### O que foi feito:
1. **export.py** — `ExportHtmlRequest` ganhou campos opcionais: `slide_index`, `page_size`, `resolution`. Route passa params às funções de serviço e detecta retorno ZIP para multi-imagem.

2. **file_service.py** — Adicionadas tabelas de viewport (`_PAGE_VIEWPORTS`, `_RES_VIEWPORTS`). `generate_pdf_playwright`: viewport dinâmico por page_size, seleção de slide específico, reportlab pagesize dinâmico. `html_to_screenshot`: viewport por resolução, ZIP com todas as imagens quando multi-slide sem slide_index. `html_to_pptx`: viewport dinâmico, slide_index, dimensões PPTX dinâmicas em EMUs.

3. **DesignPreviewModal.tsx** — Painel inline de opções de export (só para apresentações): escolha de slides (todos ou atual), tamanho da página (Widescreen/A4/Letter) para PDF/PPTX, resolução (HD/Full HD) para PNG/JPEG. `downloadHtmlExport` passa opções extras e detecta ZIP. Designs single-page mantêm export direto sem opções.

### Por quê:
Usuário pediu que na hora de baixar apresentações, pudesse escolher quais slides exportar e em que formato/tamanho. O design deve se ajustar responsivamente ao formato escolhido (viewport do Playwright muda antes da captura, CSS responsivo reflui o conteúdo).

---

## 2026-03-27 01:00 — Claude Code (claude-opus-4-6) — Fix multi-slide: preview, modal, export

### Arquivos modificados:
- `components/chat/PresentationCard.tsx`
- `components/chat/DesignPreviewModal.tsx`
- `backend/services/file_service.py`

### O que foi feito:
1. **PresentationCard.tsx** — Reescrito para detectar apresentações multi-slide (regex em `.slide` class). Para apresentações: thumbnail 16:9 (não quadrado), mostra apenas o 1o slide, badge com contagem de slides, remove scripts de navegação do thumbnail. Para designs single-page: mantém comportamento original (1:1 square).

2. **DesignPreviewModal.tsx** — Adicionado modo apresentação automático. Quando detecta multi-slide: usa iframe viewer com navegação de slides (prev/next, dots, teclado, postMessage), sem Fabric.js. Export envia o HTML original ao backend (não um PNG do canvas). Para designs single-page: mantém Fabric.js editor com sidebar.

3. **file_service.py** — `generate_pdf_playwright`: agora detecta `.slide, .slide-container` e gera PDF multi-página (screenshot por slide + reportlab). `html_to_screenshot`: mostra apenas o 1o slide em apresentações. `html_to_pptx`: seletor atualizado para `.slide, .slide-container` (consistência).

### Por quê:
Bug reportado: apresentação com 10 slides aparecia toda sobreposta no thumbnail (forçava 1080x1080 quadrado), o modal Fabric.js só capturava 1 slide, e o PDF tinha apenas 1 página. Root cause: todo o sistema de preview/edit/export era projetado para designs single-page (posters, cards), não apresentações multi-slide.

---

## 2026-03-26 23:59 — Claude Code (claude-opus-4-6)

### Arquivos modificados:
- `backend/agents/orchestrator.py`

### O que foi feito:
1. **orchestrator.py** — Corrigido acknowledgment do planner em planos complexos: agora é enviado como `pre_action` (bolha temporária) em vez de `chunk`, para não poluir o conteúdo do step terminal. Anteriormente, o acknowledgment era concatenado com o HTML do design_generator nos chunks, fazendo o frontend não detectar `<!DOCTYPE` no início e renderizar o HTML como texto cru ao invés do PresentationCard.

### Por quê:
Bug reportado: ao pedir uma apresentação (fluxo deep_research → slide_generator → design_generator), o HTML gerado era exibido como texto cru no chat ao invés de abrir o PresentationCard. Causa: o acknowledgment do planner ("Ok, vou pesquisar...") era enviado como `chunk` antes do HTML, quebrando a detecção `startsWith('<!DOCTYPE')` no frontend.

---

## 2026-03-26 — Claude Code (claude-sonnet-4-6) — Skill: Gerador de Slides (slide_generator)

### Arquivos criados:
- `backend/skills/slide_generator.py`

### Arquivos modificados:
- `backend/agents/prompts.py`

### O que foi feito:
1. **slide_generator.py** — Primeira skill de negócio do Arcco. Modelos Pydantic `Slide` e `SlideDeck` definem a estrutura: layout (`title_and_subtitle` | `bullets` | `big_number`), heading, points, big_value e speaker_notes. A função `execute()` injeta o JSON schema no system prompt (padrão do planner), chama `call_openrouter` com o modelo do agente `text_generator`, valida o output com `SlideDeck.model_validate()` e retorna JSON. Keywords: slide, slides, apresentação, pitch, deck, powerpoint, pptx, keynote, palestra.
2. **prompts.py** — Adicionado Exemplo 5 ao PLANNER_SYSTEM_PROMPT: quando `slide_generator` está disponível nas SKILLS DE NEGÓCIO, o planner deve usar o fluxo `web_search → slide_generator → design_generator` no lugar de `text_generator → design_generator` para apresentações.

### Por que:
A skill atua como copywriter estruturado que antecede o design_generator, produzindo um JSON com decisões de layout, copy e notas do palestrante por slide. O design_generator recebe esse JSON rico e gera HTML de qualidade muito superior ao que recebia via texto livre.

---

## 2026-03-26 — Claude Code (claude-sonnet-4-6) — Sistema à prova de troca de modelos

### Arquivos criados:
- `backend/core/model_capabilities.py`

### Arquivos modificados:
- `backend/core/llm.py`
- `backend/agents/orchestrator.py`

### O que foi feito:
1. **model_capabilities.py** — Cache de capacidades aprendido em runtime. Dois conjuntos: `_NO_FORCED_TOOL_CHOICE` (modelos que rejeitam tool_choice forçado) e `_NO_TOOLS` (modelos sem function calling). API: `supports_forced_tool_choice()`, `mark_no_forced_tool_choice()`, `supports_tools()`, `mark_no_tools()`, `get_summary()`.
2. **llm.py** — `_normalize_message()`: remove blocos `<think>...</think>` do content antes de qualquer processamento (DeepSeek R1, QwQ, Marco-o1, etc. jogam reasoning tokens inline). Aplicado automaticamente em todos os choices de toda chamada `call_openrouter`.
3. **orchestrator.py** — `_call_supervisor_for_step` reescrito: (a) consulta o cache ANTES da chamada — modelos já conhecidos como "sem forced tool_choice" vão direto para "auto" sem round-trip de erro; (b) detecta e classifica erros de tool_choice vs erro de tools completo; (c) `mark_*` atualiza o cache na primeira falha; (d) retry de reforço usa o cache para não repetir o erro.

### Por que:
Troca frequente de modelos (especialmente chineses baratos) causava falhas imprevisíveis: tool_choice 404, thinking tokens poluindo o pipeline, erros crypticos sem mensagem útil. Agora o sistema adapta automaticamente na primeira requisição e performa otimamente em todas as seguintes.

---

## 2026-03-26 — Claude Code (claude-sonnet-4-6) — Fix: fallback tool_choice para modelos sem suporte

### Arquivos modificados:
- `backend/agents/orchestrator.py`

### O que foi feito:
1. **orchestrator.py** — `_call_supervisor_for_step`: adicionado try/except ao redor da chamada `call_openrouter` com `tool_choice` forçado. Quando o modelo retorna erro 404 com "No endpoints found that support the provided 'tool_choice' value" (modelos como `xiaomi/mimo-v2-pro` via OpenRouter), o sistema faz fallback automático para `tool_choice="auto"` e injeta instrução textual para guiar o modelo. O mesmo fallback foi adicionado na segunda tentativa (retry).

### Por que:
Modelo `xiaomi/mimo-v2-pro` configurado no admin não suporta `tool_choice` forçado. O OpenRouter retornava 404 imediatamente, derrubando toda a execução. O fallback garante compatibilidade com qualquer modelo do OpenRouter independente do suporte a tool_choice estrito.

---

## 2026-03-26 — Claude Code (claude-sonnet-4-6) — Arquitetura Híbrida: Motor de Skills Dinâmicas

### Arquivos criados:
- `backend/skills/__init__.py`
- `backend/skills/base.py`
- `backend/skills/loader.py`

### Arquivos modificados:
- `backend/agents/orchestrator.py`
- `backend/agents/planner.py`

### O que foi feito:
1. **backend/skills/__init__.py** — Marca o diretório como módulo Python com instruções de template para criar novas skills.
2. **backend/skills/base.py** — TypedDict `SkillMeta` documentando o contrato que cada skill deve seguir: `id`, `name`, `description`, `parameters` (JSON Schema).
3. **backend/skills/loader.py** — Motor de autodescoberta: usa `pkgutil.iter_modules` para encontrar todos os arquivos `.py` em `backend/skills/` que expõem `SKILL_META + execute()`. API pública: `get_skill_tool_definitions()`, `is_skill()`, `get_skill_ids()`, `get_skill_descriptions()`, `execute_dynamic_skill()`.
4. **orchestrator.py** — 6 mudanças cirúrgicas:
   - Import de `skills_loader` no topo.
   - `active_tools` agora concatena `skills_loader.get_skill_tool_definitions()`.
   - TOOL_MAP lookup no Planner Loop: fallback para `route = "dynamic_skill"` quando `func_name` não está no TOOL_MAP mas é uma skill válida.
   - `elif route == "dynamic_skill":` no Planner Loop: chama `execute_dynamic_skill`, acumula contexto.
   - TOOL_MAP lookup no ReAct Loop: mesmo fallback.
   - `elif route == "dynamic_skill":` no ReAct Loop: chama `execute_dynamic_skill`, adiciona a `current_messages`.
5. **planner.py** — Injeção dinâmica: antes de chamar o LLM, injeta descrições das skills disponíveis no system prompt do planner para que ele saiba quando usá-las.

### Por que:
Cada nova integração de negócio (CNPJ, rastreador, cotação, WhatsApp, ERP, etc.) exigia modificar o núcleo do orchestrator.py. A nova arquitetura híbrida separa as ferramentas nativas (browser, python, design) das skills de negócio: adicionar uma nova skill agora exige apenas criar um arquivo `.py` em `backend/skills/` e reiniciar o backend.

---

## 2026-03-25 — Claude Code (claude-sonnet-4-6) — Spy Pages card: fix canais de tráfego e gênero

### Arquivos modificados:
- `components/chat/SpyPagesInputCard.tsx`

### O que foi feito:
1. **Canais de tráfego** — Barras corrigidas para usar a porcentagem real (0–100%) como largura CSS, em vez de largura relativa ao maior canal (que distorcia as proporções visualmente). Organic/paid pills movidos para rodapé discreto abaixo das barras, como texto simples com ponto separador.
2. **Gênero** — Substituída barra dividida (fina, difícil de ler) por dois blocos stat lado a lado: azul para ♂ Masculino e rosa para ♀ Feminino, mostrando porcentagem em destaque. Seção agora sempre renderiza (mostra "—" quando Apify não retorna os dados), eliminando o sumiço do bloco.

### Por que:
Barra relativa ao max exibia proporções enganosas (canal de 30% aparecia igual ao de 60%). Barra de gênero era fina demais e sumia quando dados eram null — dois blocos coloridos são mais claros e resilientes a dados ausentes.

---

## 2026-03-25 — Claude Code (claude-sonnet-4-6) — Spy Pages card: melhorias visuais de demografia

### Arquivos modificados:
- `components/chat/SpyPagesInputCard.tsx`

### O que foi feito:
1. **SpyPagesInputCard.tsx** — Seção "Audiência" do SitePreviewCard melhorada em dois pontos:
   - **Gênero**: labels coloridos com `text-blue-400` (♂) e `text-pink-400` (♀) mostrando porcentagem diretamente ao lado do símbolo. Barra split masculino/feminino com `bg-blue-500` / `bg-pink-400`.
   - **Idade**: substituídas barras verticais (histograma com porcentagem só no tooltip) por barras horizontais com label da faixa (ex: "18-24") à esquerda e porcentagem visível à direita. Maxval calculado fora do `.map()` via IIFE para evitar recálculo por item.

### Por que:
Usuário pediu: distribuição etária com porcentagem visível + distribuição masculina/feminina com rótulos coloridos e identidade visual clara.

---

## 2026-03-23 — Claude Code (claude-sonnet-4-6) — Spy Pages Tool: análise de tráfego via SimilarWeb/Apify

### Arquivos modificados:
- `backend/core/config.py`
- `backend/services/apify_service.py` (NOVO)
- `backend/agents/tools.py`
- `backend/agents/executor.py`
- `backend/agents/orchestrator.py`
- `backend/api/chat.py`
- `backend/tools/catalog.py`
- `lib/api-client.ts`
- `components/chat/SpyPagesInputCard.tsx` (NOVO)
- `components/chat/SpyPagesResultCard.tsx` (NOVO)
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **config.py** — Adicionado campo `apify_api_key`, carregado de env `APIFY_API_KEY` e de provider='apify' no Supabase.
2. **apify_service.py** — Novo serviço: chama actor `tri_angle~similarweb-scraper` via Apify REST API síncrona. Normaliza campos (visits, bounce, países, páginas, concorrentes, keywords).
3. **tools.py** — Adicionado `SPY_PAGES_TOOLS` com tool `analyze_web_pages(urls[])`.
4. **executor.py** — Handler `_analyze_web_pages` que chama `apify_service.analyze_pages()`.
5. **orchestrator.py** — Import SPY_PAGES_TOOLS, TOOL_MAP entry, param `spy_pages_enabled`, `active_tools` dinâmico, handler spy_pages no planner loop E no ReAct loop. Corrigido `_call_supervisor_for_step` para receber `tools` como parâmetro (era referência inválida a variável local). Corrigido ReAct loop de `SUPERVISOR_TOOLS` hardcoded para `active_tools`.
6. **chat.py** — Extrai `spy_pages_enabled` do body e passa ao orquestrador.
7. **catalog.py** — Entry spy_pages na loja de tools.
8. **api-client.ts** — Param `spyPagesEnabled`, event type `spy_pages_result` e `pre_action`, handler especial no SSE loop para evento com campo `data` em vez de `content`.
9. **SpyPagesInputCard.tsx** — Card de input com 1-4 URLs, botão "Iniciar análise".
10. **SpyPagesResultCard.tsx** — Card de resultado com tabs (Visão Geral, Audiência, Concorrentes), selector de site, métricas, botão "Gerar relatório".
11. **ArccoChat.tsx** — States `spyPagesActive`, `spyPagesEnabled`, `spyPagesResult`, `showToolsDropdown`. Botão "Tools" vira dropdown. Handler SSE `spy_pages_result`. `handleSpyPagesSubmit`. Render dos 2 novos cards.

### Por que:
Implementação completa da tool Spy Pages: permite ao usuário analisar tráfego de até 4 sites via SimilarWeb (usando Apify), com resultado interativo em card com abas diretamente no chat.

## 2026-03-22 — Claude Code (claude-opus-4-6) — Botao Computer no Chat: IA manipula arquivos do usuario

### Arquivos modificados:
- `backend/agents/tools.py`
- `backend/agents/executor.py`
- `backend/agents/orchestrator.py`
- `backend/api/chat.py`
- `lib/api-client.ts`
- `pages/ArccoChat.tsx`
- `pages/ArccoComputer.tsx`
- `App.tsx`

### O que foi feito:
1. **tools.py** — Adicionado `COMPUTER_TOOLS` com 3 tools: `list_computer_files`, `read_computer_file`, `manage_computer_file` (move/rename/create_folder/save_new).
2. **executor.py** — Adicionado `user_id` param no `execute_tool()`. Implementados 3 handlers: `_list_computer_files` (query Supabase user_files), `_read_computer_file` (fetch blob + extrai texto via `_extract_text_from_bytes`), `_manage_computer_file` (switch por action).
3. **orchestrator.py** — Adicionados params `user_id` e `computer_enabled`. Quando `computer_enabled=True`, inclui COMPUTER_TOOLS no array de tools do supervisor e adiciona instrucao no prompt. Adicionadas 3 entradas no TOOL_MAP (non-terminal, route "computer"). Todas as chamadas `execute_tool()` recebem `user_id`.
4. **chat.py** — Extrai `computer_enabled` do body e passa pro `orchestrate_and_stream()` junto com `user_id`.
5. **api-client.ts** — Adicionado param `computerEnabled` na funcao `chat()`, enviado como `computer_enabled` no body.
6. **ArccoChat.tsx** — Adicionado state `computerEnabled`, botao toggle "Computer" no toolbar (so aparece em modo agente), passa flag na chamada `agentApi.chat()`. Removido props `pendingFileIds`/`onPendingFilesConsumed` e useEffect de upload intermediario.
7. **ArccoComputer.tsx** — Removido prop `onOpenChatWithFiles`, funcao `handleOpenWithAI` e botao "Abrir com IA".
8. **App.tsx** — Removido state `pendingFileIds`, props `pendingFileIds`/`onPendingFilesConsumed` do ArccoChatPage, e callback `onOpenChatWithFiles` do ArccoComputerPage.

### Por que:
Novo fluxo: toggle "Computer" no input do chat permite a IA acessar diretamente os arquivos do usuario no Supabase (listar, ler, mover, renomear, criar pasta, salvar novo). Elimina o fluxo intermediario de "Abrir com IA" que fazia upload duplicado. Codigo mais limpo e experiencia mais direta.

---

## 2026-03-22 — Claude Code (claude-sonnet-4-6) — ArccoComputer UI/UX refinement

### Arquivos modificados:
- `pages/ArccoComputer.tsx`

### O que foi feito:
1. **ArccoComputer.tsx** — Removido ícone Monitor do título, `text-2xl font-bold` → `text-xl font-semibold`. Upload button: `rounded-xl` → `rounded-md`. Nova Pasta button: removido `bg-[#1a1a1a]`, simplificado para `border border-neutral-700 hover:text-white rounded-md`. Drag overlay: removido `bg-indigo-500/10 border-2 border-dashed` e card interno, substituído por `bg-black/50` simples. Spinner de loading: `h-8 w-8` → `h-5 w-5`, cor `border-neutral-500`. Empty state: removido `border-2 border-dashed border-[#262626] rounded-2xl`. Folder hover: `hover:border-indigo-500/40` → `hover:border-neutral-700`. File grid card selected: removido `ring-1 ring-indigo-500/30`. Download hover button: removido `backdrop-blur-sm`. File list card selected: removido `ring-1 ring-indigo-500/20`. Action bar: todos os `rounded-xl` → `rounded-md`; botão Mover/Renomear: `border border-neutral-700 hover:text-white`; botão Excluir: `border border-neutral-700 hover:border-red-500/30 text-red-400`. Modais Nova Pasta e Mover: `rounded-2xl` → `rounded-xl`, input `rounded-xl` → `rounded-lg`, botões Criar/Mover: `rounded-xl` → `rounded-md`. Modal Mover folder selected: `bg-indigo-500/15 border-indigo-500/50 text-indigo-200` → `bg-white/[0.07] text-white border-transparent`.

### Por que:
UI do Arcco Computer tinha padrões visuais típicos de geração por IA (anel duplo ring/border, empty state com dashed border, drag overlay dramático, rounded-xl em tudo, hover colorido indigo). Padronizado com o sistema de botões e estilos da plataforma.

---

## 2026-03-22 — Claude Code (claude-opus-4-6) — Session files fix

### Arquivos modificados:
- `pages/ArccoChat.tsx`
- `pages/ArccoComputer.tsx`

### O que foi feito:
1. **ArccoChat.tsx** — Reescrito useEffect de `pendingFileIds`: agora faz fetch do blob do Supabase Storage, cria File object, e faz upload real via `agentApi.uploadSessionFile()`. Antes so criava metadados locais sem enviar pro backend.
2. **ArccoComputer.tsx** — Corrigido userId: removido `supabase.auth.getUser()` (nao funciona com service_role key), agora usa `localStorage.getItem('arcco_user_id')` via prop do App.tsx.

### Por que:
O botao "Abrir com IA" do Arcco Computer nao enviava os arquivos pro backend como session files. O agente precisa dos arquivos em `/tmp/arcco_chat/{session_id}/` para poder le-los via `read_session_file`.

---

## 2026-03-22 — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `components/Sidebar.tsx`
- `pages/ArccoChat.tsx`
- `components/SettingsModal.tsx`
- `pages/AdminPage.tsx`

### O que foi feito:
1. **Sidebar.tsx** — NavButton active state: removido gradiente `from-indigo-500/10` e glow `shadow-[0_0_20px...]`, substituído por `bg-white/[0.06]` simples. Ícone ativo: removido `drop-shadow` glowing. Border-radius dos botões de nav: `rounded-xl` → `rounded-lg`. Todos os inputs e botões do modal "Novo Projeto": `rounded-xl` → `rounded-lg`/`rounded-md`. Botão Tools active state: mesmo simplificação do NavButton.
2. **ArccoChat.tsx** — Botão Enviar: `bg-neutral-800 rounded-lg` → `bg-white/[0.08] rounded-md`. Botão Plus/Anexar: `rounded-full` → `rounded-md`. Botões Tools e Pesquisa da toolbar: `rounded-full px-2 py-1` → `rounded-md`. Mode Toggle: removida borda `border-[#333]`, agora é apenas texto com `hover:bg-white/[0.05]`. Suggestions: `rounded-full` → `rounded-md`. Botão Parar: `rounded-full backdrop-blur-sm` → `rounded-lg` sem blur. FilePreviewCard: Download e Salvar com `border border-neutral-700` em vez de `bg-[#1a1a1a]`.
3. **SettingsModal.tsx** — Tabs laterais: removido `border-indigo-500/20` do estado ativo, agora usa `bg-white/[0.07]` sem borda colorida. Todos os inputs: `rounded-xl` → `rounded-lg`. Botão Save, Atualizar Senha, Assinar, Nova Tarefa: `rounded-xl` → `rounded-md`.
4. **AdminPage.tsx** — Tabs de navegação: `bg-indigo-500/20 text-indigo-300 border border-indigo-500/30` → `bg-[#1c1c1c] text-white` sem borda colorida. Botão Save dos agentes e chat slots: `bg-indigo-500/20 text-indigo-300 border border-indigo-500/30` → `bg-indigo-600 text-white rounded-md`. Botão Delete chat slot: sem bg vermelho, apenas `text-red-400` com borda neutra. Botão "Novo modelo": `bg-indigo-500/20 text-indigo-300` → `bg-indigo-600 text-white rounded-md`.

### Por que:
UI/UX refinement para eliminar padrões que fazem a interface parecer "gerada por IA": excesso de `rounded-xl`, gradientes e glows em active states, e o pattern `bg-indigo-500/20 text-indigo-300 border border-indigo-500/30` usado em demasia. Simplificação para hierarquia visual mais clara e identidade mais humana.

---


## 2026-03-22 — Claude Code (claude-opus-4-6)

### Arquivos modificados:
- `lib/driveService.ts`
- `types.ts`
- `components/Sidebar.tsx`
- `pages/ArccoComputer.tsx` (novo)
- `App.tsx`
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **driveService.ts** — Adicionado `folder_path` na interface `UserFile`. Novos metodos: `listByFolder`, `listFolders`, `createFolder`, `moveFile`, `renameFile`, `uploadMultiple`, `getFilesByIds`.
2. **types.ts** — Adicionado `ARCCO_COMPUTER` ao tipo `ViewState`.
3. **Sidebar.tsx** — Renomeado "Arcco Drive" para "Arcco Computer" com icone `Monitor`. Navegacao aponta para `ARCCO_COMPUTER`.
4. **ArccoComputer.tsx** — File manager completo: breadcrumb, pastas, selecao multipla, upload drag-drop, criar pasta, mover, renomear, excluir, busca, botao "Abrir com IA".
5. **App.tsx** — Import atualizado para `ArccoComputerPage`. Adicionado estado `pendingFileIds`. Rota `ARCCO_COMPUTER` com callback `onOpenChatWithFiles`. Props `pendingFileIds`/`onPendingFilesConsumed` passadas ao ArccoChat.
6. **ArccoChat.tsx** — Novas props `pendingFileIds` e `onPendingFilesConsumed`. useEffect que carrega arquivos do Computer como attachments com toast de confirmacao.

### Por que:
Transformar o "Arcco Drive" (cofre simples) no "Arcco Computer" — file manager com pastas, upload multiplo e integracao com o chat para manipular arquivos via IA.

---

## 2026-03-21 (light-theme-fix) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `src/index.css`
- `components/SettingsModal.tsx`

### O que foi feito:
1. **SettingsModal.tsx** — Reduziu temas de 5 para 3 (removeu `dim` e `midnight`). Grid mudou de `grid-cols-5` para `grid-cols-3`. Swatch do light atualizado para `#ededef` sem grid.
2. **index.css** — Reescrita completa do bloco `[data-theme="light"]`: fundo `#ededef` (cinza suave), sem dot-grid, sombra ambiente sutil via glow-primary/secondary. Overrides CSS abrangentes para todos os hardcodes de cor encontrados nos componentes: `bg-[#0a0a0a]/80`, `bg-[#111113]`, `bg-[#121212]/95`, `bg-[#1a1a1d]`, `bg-[#141416]`, `bg-[#222]`, `bg-[#252525]`, e todos os `border-[#xxx]`. Inversão da paleta Tailwind v4 via `--color-neutral-*`. Botões indigo forçam `color: white`. Scrollbar clara.

### Por quê:
Light theme tinha falhas visuais graves (inputs escuros, sidebar quebrada, botões sem contraste) porque apenas variáveis CSS genéricas eram sobrescritas. Fix cobre todas as cores hardcoded Tailwind arbitrary values usadas nos componentes via seletores CSS `[data-theme="light"] .class-name`.

---

## 2026-03-21 (clarificacao) — Claude Opus 4.6

### Arquivos modificados:
- `backend/agents/planner.py`
- `backend/agents/prompts.py`
- `backend/agents/orchestrator.py`
- `lib/api-client.ts`
- `pages/ArccoChat.tsx`
- `components/chat/ClarificationCard.tsx` (novo)

### O que foi feito:
1. **planner.py** — Adicionados ClarificationQuestion, acknowledgment, needs_clarification e questions ao PlannerOutput.
2. **prompts.py** — Regras de quando clarificar vs seguir direto no PLANNER_SYSTEM_PROMPT.
3. **orchestrator.py** — Emite acknowledgment (chunk) e clarification (SSE) antes do pipeline. Se needs_clarification, pausa e retorna.
4. **api-client.ts** — Adicionado 'clarification' ao ChatStreamEventType.
5. **ClarificationCard.tsx** — Novo componente com radio buttons (choice) e text input (open), botao Continuar.
6. **ArccoChat.tsx** — Estado clarificationQuestions, handler SSE, renderizacao condicional do card, limpeza no handleSendMessage.

### Por que:
Pedidos ambiguos geravam resultados genericos. Agora o planner pode fazer perguntas antes de executar, melhorando a qualidade das respostas. Inspirado no Claude Code e Manus.

---

## 2026-03-21 (temas) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `src/index.css`
- `components/SettingsModal.tsx`

### O que foi feito:
1. **index.css** — Adicionado tema `ghost`: dark plano sem decorações (`--dot-color: transparent`, `--glow-primary/secondary: transparent`). Adicionado tema `light`: off-white (`#f5f5f7`) com inversão da paleta de neutros Tailwind v4 via CSS vars (`--color-neutral-*`, `--color-white`) + scrollbar clara.
2. **SettingsModal.tsx** — Array `themes` expandido de 3 para 5 (+ ghost + light). Grid trocado de `flex` para `grid grid-cols-5 gap-2`. Swatch sem linha quando `line === 'transparent'`.

### Por quê:
Os 3 temas existentes eram praticamente idênticos (variações de preto). Adicionados `Ghost` (dark limpo sem background decorativo) e `Light` (claro com inversão da paleta de cores).

---

## 2026-03-21 — Claude Opus 4.6

### Arquivos modificados:
- `backend/agents/planner.py`
- `backend/agents/prompts.py`
- `backend/agents/orchestrator.py`

### O que foi feito:
1. **planner.py** — Adicionado campo `is_terminal` (bool, default=False) ao PlanStep. Permite que o planner decida qual step encerra o pipeline.
2. **prompts.py** — Adicionadas regras de "FLUXO E TERMINAL" ao PLANNER_SYSTEM_PROMPT com 3 exemplos concretos de fluxo correto.
3. **orchestrator.py** — No planner loop: (a) fallback de seguranca que forca ultimo step como terminal se planner esqueceu; (b) refatorado bloco `elif is_terminal:` para checar `step.is_terminal` em vez de `TOOL_MAP` hardcoded. Steps nao-terminais acumulam resultado no `accumulated_context` e continuam. ReAct loop inalterado.

### Por que:
O pipeline parava prematuramente quando `text_generator` executava antes de `design_generator` num plano multi-step, porque `text_generator` era hardcoded como terminal. Agora o planner controla o fluxo e apenas o ultimo step entregavel e terminal.

## 2026-03-21 — Claude Opus 4.6 (Logs de observabilidade)

### Arquivos modificados:
- `backend/agents/orchestrator.py`

### O que foi feito:
1. **orchestrator.py** — Adicionados 4 novos pontos de log no planner loop:
   - `terminal_fallback` (warning): quando o fallback de seguranca forca o ultimo step como terminal
   - `pipeline_terminated`: quando o pipeline para num step terminal, com lista de steps pulados
   - `context_accumulated`: quando um step nao-terminal acumula resultado, com tamanho do contexto
   - `step_skipped` (error): quando o supervisor ignora a tool forcada e responde em texto
   - `planner_step_started` agora inclui `accumulated_context_chars` no payload

### Por que:
Melhorar diagnosticabilidade na aba de Logs do admin. Agora cada decisao do pipeline (parar, acumular, pular) fica registrada no Supabase com dados concretos.

---

## 2026-03-21 (19) — Claude Code (claude-opus-4-6)

### Arquivos modificados:
- `backend/agents/prompts.py`

### O que foi feito:
1. **DESIGN_GENERATOR_SYSTEM_PROMPT** — Adicionada secao "APRESENTACOES E MULTIPLAS ARTES":
   - Instrui o agente a gerar cada slide como HTML COMPLETO e INDEPENDENTE
   - Separa slides com `<!-- ARCCO_DESIGN_SEPARATOR -->`
   - Nunca juntar multiplos slides num unico HTML
   - Inclui exemplo de saida com 2 slides
   - Adicionada regra de dimensao fixa 1080x1080px

### Por que:
O frontend ja tinha toda a logica de split por DESIGN_SEPARATOR (renderContent em ArccoChat.tsx → DesignGallery → DesignPreviewModal com tabs), mas o prompt do design_generator nao instruia o agente a usar o separador. Resultado: apresentacoes vinham como um HTML gigante com tudo junto, sem galeria nem tabs no editor.

---

## 2026-03-20 (18) — Claude Code (claude-opus-4-6)

### Arquivos modificados:
- `components/chat/DesignPreviewModal.tsx`

### O que foi feito:
1. **FIX: textos nao eram extraidos** — `EDITABLE_TAGS` (Set com H1-H6, P, SPAN, etc.) nao incluia `DIV`, mas a IA gera HTML com texto dentro de `<div>`. O filtro `if (!EDITABLE_TAGS.has(el.tagName)) continue` pulava TODOS os textos → array `texts` vazio → nenhum Textbox no canvas → edicao impossivel.
2. **Nova abordagem: leaf detection** — Removido filtro por tag. Nova funcao `collectLeafTextElements()` coleta TODOS os elementos com texto visivel, depois remove wrappers via `el.contains(other)` — mantendo apenas os mais internos (folhas). Isso garante que textos em qualquer tag (div, p, h1, span, etc.) sejam capturados sem duplicatas.
3. **Removido `EDITABLE_TAGS`** — nao mais necessario.

### Por que:
O preview ficava perfeito (html2canvas captura tudo como imagem), mas nao havia nenhum objeto editavel no canvas Fabric.js porque o filtro por tag descartava os elementos `<div>` onde a IA coloca o texto.

---

## 2026-03-20 (17) — Claude Code (claude-opus-4-6)

### Arquivos modificados:
- `components/chat/DesignPreviewModal.tsx`
- `package.json` (dependencias: fabric, html2canvas)

### O que foi feito:
1. **Refatoracao completa: iframe → Fabric.js canvas**
   - Instalado `fabric` v7.2.0 e `html2canvas` como dependencias
   - Removido TODO o codigo baseado em iframe (srcDoc, contentEditable, DOM manipulation, event listeners)
   - Nova arquitetura:
     a. HTML da IA renderiza em iframe OCULTO (para Tailwind CDN funcionar)
     b. `html2canvas` captura background sem texto → dataURL
     c. Textos extraidos via `getBoundingClientRect` + `getComputedStyle`
     d. Canvas Fabric.js montado: imagem de fundo + Textbox para cada texto
   - Edicao de texto: Fabric.js Textbox nativo (click para selecionar, double-click para editar inline, drag para mover, handles para redimensionar)
   - Sidebar: controles de texto (conteudo, tamanho, alinhamento, cor, fonte) que atualizam o objeto Fabric diretamente
   - Export PNG/JPEG: client-side via `canvas.toDataURL()` (sem backend)
   - Export PDF/PPTX: PNG embrulhado em HTML simples, enviado ao endpoint existente
   - Multi-design: dispose canvas + reprocessar HTML ao trocar tab
   - Escala: `canvas.setZoom()` + `setDimensions()` para caber no container
   - Loading state com spinner enquanto html2canvas processa (~500ms)

### Por que:
A abordagem iframe+contentEditable era fundamentalmente fragil: srcDoc reativo destruia edicoes, contentEditable conflitava com drag handlers, event listeners nao tinham cleanup adequado, e CSS transform causava bugs de coordenadas. Fabric.js resolve todos esses problemas com edicao, drag, resize e export nativos.

---

## 2026-03-20 (16) — Claude Code (claude-opus-4-6)

### Arquivos modificados:
- `components/chat/DesignPreviewModal.tsx`

### O que foi feito:
1. **FIX srcDoc reativo** — `initialSrcDoc` era recalculado a cada render (qualquer mudanca de cor/fonte recriava o srcDoc → iframe recarregava → destruia edicoes). Agora `srcDoc` e um `useMemo` que so depende de `iframeSrcKey`, mudancas de estilo vao direto no DOM via `applyGlobalStyles()`.
2. **FIX cleanup de event listeners** — `onLoad` retornava funcao de cleanup como callback de evento (ignorado pelo browser). Agora usa `cleanupRef` para armazenar e chamar cleanup corretamente no useEffect.
3. **Removido drag-and-drop** — conflitava fundamentalmente com contentEditable (mousedown do drag impedia cursor de texto). Edicao inline agora funciona normalmente.
4. **Edicao inline + sidebar** — clique no texto da arte coloca cursor para edicao direta, sidebar mostra controles (texto, tamanho, alinhamento, cor). Ambos funcionam sem conflito.
5. **Export limpo** — remove contenteditable/spellcheck/selection antes de serializar, restaura depois.

### Por que:
O editor estava completamente quebrado: nenhuma edicao funcionava porque o srcDoc era recalculado em toda mudanca de estado, recarregando o iframe. Event listeners se acumulavam sem cleanup. Drag-and-drop impedia edicao de texto.

---

## 2026-03-20 (15) — Claude Code (claude-opus-4-6)

### Arquivos modificados:
- `components/chat/DesignPreviewModal.tsx`

### O que foi feito:
1. **DesignPreviewModal.tsx** — Reescrita completa da arquitetura do editor de design:
   - **Fix edicao de texto**: Removido padrao reativo srcDoc (causava reload do iframe a cada keystroke, destruindo estado de edicao). Agora usa `iframeSrcKey` counter para reloads controlados + manipulacao direta do DOM do iframe para todas as edicoes.
   - **Fix posicionamento**: Design ficava preso no canto. Implementado sistema de escala dinamica com `transform: scale()` calculado como `Math.min(iframeWidth/1080, iframeHeight/1080)`, centralizando com margins automaticas.
   - **Drag and drop**: Implementado arraste de elementos com `translate()` transform, coordenadas escaladas pelo fator de viewport, threshold de 4px para distinguir clique de arraste.
   - **Export limpo**: `getExportHtml()` remove temporariamente escala/margins antes de serializar, garantindo que o download reflete exatamente o que o usuario ve no canvas.
   - **Clareza visual**: Borda tracejada ao redor do canvas, footer com "O que voce ve na moldura e exatamente o que sera baixado", dropdown com texto explicativo.
   - **Novos helpers**: `parseTranslate()`, `rgbToHex()`, `parseFontSize()`, `applyScale()`, `applyGlobalStyles()` (DOM direto).
   - **Sidebar expandida**: Font size slider 8-120px com input numerico, hint de drag-and-drop, alinhamento texto.

### Por que:
Edicao de texto nao funcionava (iframe recarregava a cada mudanca), design ficava no canto (body fixo em 1080px num iframe de ~600px), usuario nao sabia o que seria baixado, e nao tinha como arrastar elementos. Reescrita resolve todos esses problemas com arquitetura de manipulacao direta do DOM.

---

## 2026-03-20 (14) — Claude Code (claude-opus-4-6)

### Arquivos modificados:
- `components/chat/DesignPreviewModal.tsx`
- `src/index.css`

### O que foi feito:
1. **DesignPreviewModal.tsx** — Redesign completo do layout para estilo Canvas+Sidebar:
   - Removido toggle View/Edit — design sempre editavel, clicar num texto abre propriedades na sidebar
   - Canvas com fundo checkerboard para delimitar claramente a borda da arte (nao se perde mais no fundo escuro)
   - Shadow no container do design para destacar do fundo
   - Sidebar fixa 280px a direita com:
     - Controles do elemento selecionado: textarea, slider de tamanho de fonte (8-72px, NOVO), botoes de alinhamento esquerda/centro/direita (NOVO), cor do texto
     - Controles globais: fundo transparente/cor, cor de texto geral, cor de destaque, fonte
   - Estado vazio da sidebar: mensagem "Clique em qualquer texto da arte para editar"
   - Dropdown de export com label claro "Baixar como PNG/PDF/PPTX/JPEG"
   - Footer informativo: dimensoes "1080 x 1080px"
   - Removidos sliders de preview (zoom/borda/raio) que confundiam o usuario
   - SelectedNodeState expandido com fontSize e textAlign
   - Novos handlers: handleSelectedFontSizeChange, handleSelectedAlignChange
2. **index.css** — Adicionado `.checkerboard-bg` com padrao xadrez sutil para fundo do canvas

### Por que:
O editor de design era confuso: borda da arte se perdia no fundo escuro, usuario nao sabia onde alterar o que, nao tinha controle de tamanho de fonte nem alinhamento, e nao ficava claro o que seria baixado. O redesign estilo Canva com sidebar fixa torna tudo explicito e acessivel.

---

## 2026-03-20 (13) — Claude Code (claude-opus-4-6)

### Arquivos modificados:
- `components/chat/PresentationCard.tsx`
- `components/chat/DesignPreviewModal.tsx`

### O que foi feito:
1. **PresentationCard.tsx** — FIX CRASH: adicionado `Monitor` ao import do lucide-react. O componente usava `<Monitor>` no estado de streaming mas nao importava, causando ReferenceError que travava toda a aplicacao quando um design era gerado.
2. **DesignPreviewModal.tsx** — Redesign completo da UX do modal:
   - Header simplificado: titulo + toggle View/Edit + botao Personalizar (engrenagem) + dropdown Baixar + fullscreen + close
   - Controles de personalizacao (cores, fonte, sliders) agora ficam num painel colapsavel (fechado por padrao) — libera maximo espaco para o design
   - Botoes de export consolidados num dropdown "Baixar" no header em vez de barra separada no footer
   - Preview area ocupa todo o espaco disponivel, design centralizado vertical e horizontalmente
   - Tabs de multiplos designs simplificados (pills compactos no topo + miniaturas flutuantes no bottom do preview)
   - Painel de edicao de texto reposicionado como floating panel no canto superior direito com backdrop blur
   - Removida barra de footer com botoes de export (substituida pelo dropdown no header)
   - Visual geral mais limpo: sem cores orange excessivas, tons neutros consistentes

### Por que:
O modal travava a aplicacao inteira (crash por import faltando). Alem disso, tinha 4 barras de controles empilhadas antes do usuario ver o design — interface sobrecarregada e pouco intuitiva. O redesign prioriza o conteudo visual e esconde controles avancados atras de toggles.

---

## 2026-03-20 (12) — Claude Code (claude-opus-4-6)

### Arquivos modificados:
- `pages/ArccoChat.tsx`
- `backend/agents/orchestrator.py`

### O que foi feito:
1. **ArccoChat.tsx** — Removidos blocos legados: `AgentTerminal` (terminal card) e pill "agente · pensando▌". Substituidos por mini loading inline com logo Arcco pulsando + "Analisando..." enquanto aguarda primeiro step SSE.
2. **ArccoChat.tsx** — Removido import `AgentTerminal` e icon `Terminal` do lucide (nao mais usados).
3. **orchestrator.py** — Step inicial agora e contextual: "Entendendo o pedido: {intent}..." em vez do generico "A estruturar plano de execucao...". Segundo step trocado de thought para step: "Definindo estrategia de execucao...".

### Por que:
Remover vestigios do terminal antigo que ainda aparecia no inicio do fluxo. Fazer o agente responder prontamente com o que vai fazer, usando a intent do usuario no primeiro step emitido.

---

## 2026-03-20 (11) — Claude Code (claude-opus-4-6)

### Arquivos modificados:
- `pages/ArccoChat.tsx`
- `src/index.css`

### O que foi feito:
1. **ArccoChat.tsx** — Removido bloco `<AgentThoughtPanel>` e substituido por steps inline no fluxo de mensagens. Cada step mostra logo Arcco 16x16 pulsando (running) ou opaco (done) + texto em tom neutro. Após conclusao, steps colapsam em "X etapas · Ys" clicavel para expandir/recolher. Import do AgentThoughtPanel removido (mantido apenas o type ThoughtStep).
2. **ArccoChat.tsx** — No chunk handler, adicionado `setTimeout(() => setIsThoughtsExpanded(false), 600)` para colapso automatico dos steps quando a resposta comeca a chegar.
3. **index.css** — Adicionado keyframe `pulse-soft` (opacity 0.4→1.0, 1.5s ease-in-out infinite) e classe `.animate-pulse-soft`.

### Por que:
Substituir o painel separado (AgentThoughtPanel) por steps inline estilo Claude Code / Manus — visual mais clean e integrado ao fluxo do chat.

---

## 2026-03-20 (10) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/agents/executor.py`

### O que foi feito:
1. **executor.py** — `_execute_python`: substituiu `config.e2b_api_key or os.getenv("E2B_API_KEY")` por busca direta ao Supabase (`ApiKeys` table, providers `e2b` e `e2b_api_key`) via `asyncio.to_thread(_fetch_e2b_key_from_supabase)`. Env var / config cacheado viram fallback. Adicionado log `[E2B] Usando chave: ...` para debug.

### Por quê:
`get_config()` é singleton criado no startup. Se o servidor iniciou com `E2B_API_KEY=chave_velha` no env, o config cacheia a chave inválida e `_load_keys_from_supabase` nunca consulta o Supabase (porque `needs_e2b = not self.e2b_api_key` = False quando env var está preenchida). Resultado: 401 mesmo com chave nova no Supabase. O fix faz cada chamada E2B buscar a chave fresca do Supabase, ignorando o singleton cacheado.

---

## 2026-03-20 (9) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/agents/orchestrator.py`
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **orchestrator.py** — Complex planner loop (~linha 645): trocado `yield sse("thought", ...)` para `yield sse("pre_action", ...)` para ambos os caminhos (reasoning direto e fallback `_build_pre_action_ack`).
2. **ArccoChat.tsx** — Adicionado handler para novo evento SSE `pre_action`: seta `chatThinkingMessage` com texto do backend e ativa `chatThinkingVisible` (mostra no bubble do chat, fora do terminal).
3. **ArccoChat.tsx** — Chunk handler: removido guard `!isAgentMode` do timer de hide do thinking. Agora usa `chatThinkingStartRef.current > 0` para funcionar nos dois modos (Chat Normal e Agent). Reseta ref ao esconder.

### Por quê:
Pre-action acknowledgement precisa aparecer no bubble do chat (fora do AgentThoughtPanel/terminal). O evento `thought` ia para o terminal; o novo `pre_action` é tratado pelo frontend como indicador visual no chat bubble com mínimo 800ms de exibição.

---

## 2026-03-20 (8) — Claude Code (claude-opus-4-6)

### Arquivos modificados:
- `backend/agents/orchestrator.py`

### O que foi feito:
1. **orchestrator.py** — Criada função `_build_pre_action_ack(tool_calls)` que gera mensagens contextuais de pre-action a partir do nome da tool + argumentos (query, url, file_name). Cobre todas as 8 tools do TOOL_MAP.
2. **orchestrator.py** — ReAct simple loop (linha ~1040): refatorado check de `supervisor_reasoning` para usar `if/else` — se modelo gerou content, emite como `thought`; senão, chama `_build_pre_action_ack()` como fallback.
3. **orchestrator.py** — Complex planner loop (linha ~645): mesmo pattern de fallback adicionado — se `supervisor_reasoning` vazio mas tem `tool_calls`, gera ack contextual.

### Por quê:
O Claude (via OpenRouter) tipicamente NÃO gera `content` junto com `tool_calls` — separa os dois em mensagens distintas. A instrução no system prompt era insuficiente. O fallback `_build_pre_action_ack()` garante que uma mensagem contextual sempre aparece antes da execução de qualquer tool, independente do comportamento do modelo.

---

## 2026-03-20 (7) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/agents/prompts.py`

### O que foi feito:
1. **prompts.py** — Adicionada instrução "RECONHECIMENTO PRÉ-AÇÃO" ao final do `CHAT_SYSTEM_PROMPT`. Instrui o supervisor a escrever UMA frase curta no campo `content` antes de qualquer `tool_call`, sendo específico ao tema do pedido. Inclui exemplos por ferramenta (ask_web_search, ask_browser, execute_python, ask_design_generator, deep_research, ask_file_modifier, read_session_file).

### Por quê:
Pre-action Acknowledgement pattern — o `orchestrator.py` já tinha a infraestrutura (linhas 1036-1039) que captura `message.content` quando existe `tool_calls` e emite como evento SSE `thought`. Faltava apenas instruir o LLM a gerar esse conteúdo. Zero mudanças de código, zero mudanças no contrato SSE.

---

## 2026-03-20 (6) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **ArccoChat.tsx** — Adicionadas funções `saveConvMode` e `getConvMode` (fora do componente) que persistem o modo (agent/chat) de cada conversa no `localStorage` com a chave `arcco_conv_mode` (objeto `{ [convId]: boolean }`).
2. **ArccoChat.tsx** — No `useEffect` de carregamento de conversa por UUID, após definir `conversationId`, restaura o modo salvo via `getConvMode(chatSessionId)`.
3. **ArccoChat.tsx** — No handler SSE de `conversation_id`, chama `saveConvMode(content, isAgentMode)` para persistir o modo da conversa recém-criada.
4. **ArccoChat.tsx** — Botão de toggle de modo recebe `disabled={messages.length > 0}`, fica opaco/inativo quando há mensagens e exibe no tooltip "O modo não pode ser alterado durante uma conversa."

### Por quê:
Ao recarregar uma conversa salva, ela voltava sempre para o modo Agent (padrão). Além disso, era possível trocar de modo durante uma conversa em andamento, causando inconsistência. Agora o modo é persistido por conversa e travado após a primeira mensagem.

---

## 2026-03-20 (5) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **ArccoChat.tsx** — Substituiu `chatFirstChunkReceived` (state com race condition) por `chatThinkingVisible` (state) + `chatThinkingStartRef` + `chatThinkingTimerRef`. O panel fica visível por no mínimo 800ms: quando primeiro chunk chega, agenda `setTimeout(setChatThinkingVisible(false), max(0, 800-elapsed))`.
2. **ArccoChat.tsx** — `finally` block agora cancela o timer e força `setChatThinkingVisible(false)` em qualquer caso (erro, abort, fim normal).
3. **ArccoChat.tsx** — UI do thinking panel redesenhada estilo Google: spinner rotativo + "Pensando" + linha vertical indigo + mensagem contextual com fade-in slide-in.

### Por quê:
Race condition — `chatFirstChunkReceived` era um state React que podia ser batched com o próprio reset, tornando o indicator invisível. Novo approach usa timer explícito com tempo mínimo garantido, independente da velocidade do modelo.

---

## 2026-03-20 (4) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **ArccoChat.tsx** — Substituiu a condição `msg.content === ''` por estado dedicado `chatFirstChunkReceived`. Thinking indicator fica visível até o **primeiro chunk SSE chegar** (`setChatFirstChunkReceived(true)` no handler de `chunk`). Resetado para `false` a cada envio de mensagem em chat mode.

### Por quê:
Bug de timing — `msg.content === ''` durava apenas alguns milissegundos antes dos primeiros chunks chegarem (OpenRouter direto é rápido). Com `chatFirstChunkReceived`, a visibilidade do indicator é determinada pelo evento real de chegada de dados, não pelo estado de render do React.

---

## 2026-03-20 (3) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **ArccoChat.tsx** — Moveu o thinking indicator do Chat Normal para **dentro do bubble do assistente** (renderizado no lugar de `renderContent` quando `msg.content === ''`). Removeu o elemento separado que ficava abaixo das mensagens e não era percebido pelo usuário.

### Por quê:
Bug de UX — o indicator estava abaixo do bubble do assistente, fora do campo de visão do usuário. O assistente já aparece como placeholder vazio e começa a receber texto quase imediatamente; o usuário olha para o bubble, não para abaixo. Agora os dots e a mensagem contextual aparecem dentro do bubble, exatamente onde o usuário está olhando.

---

## 2026-03-20 (2) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **ArccoChat.tsx** — Substituiu o array fixo `chatThinkingMessages` + rotação por `useInterval` por uma função `generateThinkingMessage(text)` com keyword detection em português (15+ categorias: email, planilha, código, post, tradução, proposta, plano, análise, etc.).
2. **ArccoChat.tsx** — `chatThinkingMessage` agora é computado no momento do envio (`handleSendMessage`) baseado no texto real da pergunta do usuário.
3. **ArccoChat.tsx** — Mensagem de thinking no Chat Normal é única e contextual (sem rotação), com `animate-in fade-in` na montagem.

### Por quê:
Melhoria de UX — mensagem de thinking agora reflete o que o usuário perguntou (ex: "Redigindo a mensagem para você..." quando menciona email), tornando a experiência mais contextual e responsiva.

---

## 2026-03-20 — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **ArccoChat.tsx** — Adicionado array `chatThinkingMessages` com 7 mensagens resonantes. Adicionado estado `thinkingMsgIndex` e `useEffect` que rota as mensagens a cada 2.5s quando `!isAgentMode && isLoading`.
2. **ArccoChat.tsx** — `AgentThoughtPanel` agora só renderiza em agent mode (`isAgentMode && agentThoughts.length > 0`), removendo-o do modo Chat Normal.
3. **ArccoChat.tsx** — Indicador de loading separado por modo: agent mode mantém o pill "agente · pensando▌"; chat normal exibe 3 dots animados com mensagem resonante rotativa (fade-in via `key` trick).

### Por quê:
UX — no modo Chat Normal, o terminal e o painel de steps são informação irrelevante para o usuário. Substituído por indicador visual suave com mensagens contextuais que transmitem que o modelo está pensando.

---

## 2026-03-20 (18) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **ArccoChat.tsx** — Substituiu o dropdown de seleção de modelo (que usava `<select>` nativo invisível sobreposto em div estilizado) por um dropdown customizado completo. Adicionou estado `showChatModelDropdown`. Ambos os modos (agent e chat) agora usam dropdowns com botão trigger estilizado, painel com backdrop dismiss, ícones, checkmark no item selecionado e transição do chevron.

### Por que:
UX ruim — dropdown nativo é visualmente inconsistente com o resto da interface dark. Novo dropdown customizado segue o design system da aplicação.

---

## 2026-03-19 (17) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/ArccoChat.tsx`
- `components/chat/DesignGallery.tsx`

### O que foi feito:
1. **ArccoChat.tsx** — Importou `DesignPreviewModal`, adicionou state `designPreviewHtml`, conectou `onOpenPreview` callback no `renderContent()` para PresentationCard e DesignGallery, renderizou o modal popup condicionalmente.
2. **DesignGallery.tsx** — Adicionou prop `onOpenPreview` e repassa para cada PresentationCard. Removeu referencia a `galleryMode` (prop inexistente).

### Por que:
Conectar o fluxo completo: card compacto no chat -> click em "Visualizar" -> abre popup modal com editor/export. Sem isso os componentes estavam criados mas desconectados.

---

## 2026-03-19 (16) — Claude Code (claude-opus-4-6)

### Arquivos modificados:
- `components/chat/PresentationCard.tsx` (REWRITE)
- `components/chat/DesignGallery.tsx` (NOVO)
- `pages/ArccoChat.tsx`
- `backend/agents/prompts.py`
- `src/index.css`

### O que foi feito:
1. **PresentationCard.tsx** — Rewrite completo do editor de design. Substituiu sidebar 320px por toolbar horizontal compacta (flex-wrap). Canvas unificado responsivo (maxWidth CSS, sem altura fixa). FloatingTextPanel absoluto para editar texto selecionado. Toggle segmentado Visualizar/Editar. Barra de progresso animada no export. Prop `galleryMode` para uso dentro do gallery. Corrigidos 8 bugs: alturas fixas h-[520px]/h-[560px], Math.min(860) hardcoded, z-50 conflitante, color pickers sem touch target, sidebar que não colapsava, sem feedback de modo edição, sem feedback de export.
2. **DesignGallery.tsx** — Novo componente para exibir multiplos designs. Barra de thumbnails numerados com scroll horizontal, navegacao prev/next, contador "1 de N", renderiza PresentationCard em galleryMode.
3. **ArccoChat.tsx** — renderContent() agora faz split por `<!-- ARCCO_DESIGN_SEPARATOR -->` e renderiza DesignGallery quando ha multiplos HTML designs. Import do DesignGallery adicionado.
4. **prompts.py** — Adicionada instrucao ao DESIGN_GENERATOR_SYSTEM_PROMPT para gerar multiplas pecas separadas pelo delimiter.
5. **index.css** — 3 animacoes novas: gallery-thumb-enter, float-panel-enter, editor-glow.

### Por que:
Editor anterior tinha UX ruim (sidebar 320px inutilizavel em tablet/mobile, alturas fixas quebravam em telas menores, zero feedback visual). Nao suportava multiplos designs. Redesenhado para ser canvas-first, intuitivo e responsivo, com suporte a galeria de artes.

---

## 2026-03-19 (15) — Claude Code (claude-opus-4-6)

### Arquivos modificados:
- `backend/agents/orchestrator.py`

### O que foi feito:
1. **orchestrator.py** — Moveu `from backend.agents.tools import SUPERVISOR_TOOLS` para o topo do módulo (import global). Antes estava como import local dentro de `orchestrate_and_stream()`, mas era usado por `_call_supervisor_for_step()` (função separada) causando `NameError: name 'SUPERVISOR_TOOLS' is not defined`.

### Por quê:
Este era o BUG REAL que travava todo o fluxo de agentes. Quando o planner gerava um plano e tentava chamar o supervisor para executar o passo (web_search, browser, etc.), a função `_call_supervisor_for_step` falhava com NameError porque `SUPERVISOR_TOOLS` só existia no escopo local de `orchestrate_and_stream`. O erro era capturado pelo try/except e emitido como evento SSE de error, mas o pipeline morria ali. Testado com web_search (Tavily) e browser (Browserbase/OLX) — ambos funcionando perfeitamente com heartbeats em tempo real.

---

## 2026-03-19 (14) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/agents/orchestrator.py`

### O que foi feito:
1. **orchestrator.py** — Substituiu 4 call sites de `_run_with_heartbeat` (quebrado) por `_exec_with_heartbeat` (async generator). Os 4 pontos: web_search no planner loop, browser no planner loop, web_search no react loop, browser no react loop. Removidas referências a `_HEAVY_TOOL_TIMEOUT` (agora `_BROWSER_TIMEOUT`).

### Por quê:
O `_run_with_heartbeat` coletava heartbeats numa lista e retornava tudo junto DEPOIS da tool terminar — o frontend nunca recebia eventos SSE durante a execução, causando timeout na conexão. O novo `_exec_with_heartbeat` é um async generator que yield heartbeats em tempo real.

---

## 2026-03-19 (13) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/agents/orchestrator.py`
- `backend/api/chat.py`
- `backend/services/browser_service.py`
- `backend/services/search_service.py`
- `backend/core/config.py`
- `backend/agents/prompts.py`

### O que foi feito:
1. **orchestrator.py** — 5 correções:
   - Browser com timeout+heartbeat: envolvido `execute_tool("ask_browser")` em `_run_with_heartbeat()` (timeout 60s, heartbeat SSE a cada 5s) nos 2 locais (planner loop e react loop). Impede hang infinito e mantém conexão SSE viva.
   - Web search com timeout+heartbeat: envolvido `execute_tool("web_search")` em `_run_with_heartbeat()` (timeout 30s, heartbeat SSE a cada 5s) nos 2 locais. `web_fetch` também com `asyncio.wait_for(timeout=20)`.
   - Fallback após falha de browser: no react loop, quando browser retorna erro, injeta system message instruindo o supervisor a NÃO tentar browser novamente e usar web_search ou responder diretamente.
   - Helper `_run_with_heartbeat()`: nova função que executa coroutine com heartbeat periódico e timeout global. Cancela a task se exceder o timeout.
   - Constante `_HEAVY_TOOL_TIMEOUT = 60.0` centralizada.
2. **chat.py** — Desbloqueio do event loop: todas as chamadas sync ao Supabase em `_build_extra_context()` agora rodam via `asyncio.to_thread()`: `db.query()`, `get_user_memory()`, `search_project_context()`. Antes, chamadas httpx sync bloqueavam o event loop inteiro do uvicorn, congelando TODOS os requests durante queries ao Supabase.
3. **browser_service.py** — Timeout global de 45s no `asyncio.to_thread(_run_sync_session)` via `asyncio.wait_for()`. Proteção extra caso o CDP connection ou o site trave.
4. **search_service.py** — 3 correções:
   - `search_web_formatted()`: timeout de 10s para `get_search_key()`, timeout de 15s para `search_tavily()`/`search_brave()`. Impede hang quando Supabase ou Tavily estão lentos.
   - `search_tavily()`: timeout httpx reduzido de 30s para 15s. Logs de início/fim de busca.
   - `search_brave()`: timeout httpx reduzido de 30s para 15s. Log de início de busca.
5. **config.py** — Logs explícitos no startup: se `browserbase_api_key` ou `browserbase_project_id` estiverem vazios, loga WARNING com instruções de como configurar. Se ambos OK, loga confirmação.
6. **prompts.py** — Prompt do planner reescrito: ferramentas listadas por prioridade de uso, web_search como PRIMEIRA OPÇÃO, browser marcado como CARO E LENTO com regra explícita de só usar quando web_search não resolve. Regra crítica adicionada: "Prefira SEMPRE web_search sobre browser."

7. **llm.py** — Removido loop `["ApiKeys", "apikeys"]` em `get_api_key()`, `get_search_key()` e `get_vercel_key()`. Agora consulta APENAS a tabela `ApiKeys` (CamelCase). A tabela `apikeys` (minúscula) foi removida do Supabase pelo usuário — queries à tabela inexistente geravam erros 404 e adicionavam latência desnecessária.
8. **config.py** — Removido loop de tabelas em `_load_keys_from_supabase()`. Query única à tabela `ApiKeys`. Adicionado log dos providers encontrados no Supabase.
9. **embedding_service.py** — Removido loop de tabelas em `_get_openai_key()`. Query única à tabela `ApiKeys`.
10. **search_service.py** — Removido todo o código do Brave Search (função `search_brave()`, parâmetro `brave_key`, fallback Brave). Agora usa exclusivamente Tavily.
11. **llm.py** — `get_search_key()` busca apenas `provider=tavily` (removido loop `["tavily", "brave"]`).
12. **api/search.py** — Atualizado docstring (removido referência ao Brave).

### Por quê:
- Fluxo quebrava nas ações de busca web E browser: sem timeout em NENHUMA tool do orchestrator, qualquer lentidão no Tavily, Supabase, Browserbase ou OpenRouter travava o pipeline inteiro sem limite de tempo. Sem heartbeat, a conexão SSE era dropada pelo proxy/browser após inatividade. Chamadas sync ao Supabase bloqueavam o event loop, congelando todo o backend. Planner roteava desnecessariamente para browser quando web_search bastava.
- Tabela `apikeys` (minúscula) foi removida do Supabase, mas o código tentava queries em ambas as tabelas. Cada query à tabela inexistente gerava erro HTTP e latência extra. Unificado para usar apenas `ApiKeys`.

---

## 2026-03-19 (12) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `components/chat/AgentThoughtPanel.tsx`
- `pages/ArccoChat.tsx`
- `backend/agents/orchestrator.py`
- `backend/core/llm.py`

### O que foi feito:
1. **AgentThoughtPanel.tsx** — Aumentou visibilidade: fundo `#111114` (era `#0a0a0b`), borda `#2e2e34` quando rodando (era `#1c1c1e`), texto do header `text-neutral-300` (era `text-neutral-400`), borda esquerda do step ativo `border-neutral-300` (era `border-neutral-400`), step done `text-neutral-500` (era `text-neutral-600`), `✓` `text-neutral-600` (era `text-neutral-700`).
2. **ArccoChat.tsx** — Adicionou `useEffect` que chama `messagesEndRef.current?.scrollIntoView` quando `browserAction` muda, garantindo que o `BrowserAgentCard` seja visível ao aparecer. Atualizou loader pré-step com mesmos valores de cor.
3. **orchestrator.py** — Corrigido travamento no web_search: após receber resultado da busca, injeta mensagem `role: system` instruindo o supervisor a sintetizar e responder sem chamar mais ferramentas. Reduzido `MAX_ITERATIONS` de 5 para 3 (reduz tempo máximo de hang de 5min para ~2.5min).
4. **llm.py** — Reduzido timeout de `call_openrouter` de 60s para 45s para failar mais rápido em caso de lentidão do OpenRouter.

### Por quê:
- Travamento 4min: supervisor recebia resultado da busca e entrava em loop chamando `ask_web_search` novamente até MAX_ITERATIONS. Fix: instrução explícita para responder + menos iterações + timeout menor.
- Browser card não visível: scroll não seguia o card (apenas seguia messages). Fix: novo useEffect.
- Terminal pouco visível: cores muito escuras para o estilo escuro do tema.
- ATENÇÃO: se o BrowserAgentCard sempre mostrar erro, verificar se `BROWSERBASE_API_KEY` e `BROWSERBASE_PROJECT_ID` estão configurados (tabela ApiKeys no Supabase, provider='browserbase').

---

## 2026-03-19 (11) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `components/chat/AgentThoughtPanel.tsx` (reescrito)
- `src/index.css`
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **AgentThoughtPanel.tsx** — Reescrito do zero no estilo terminal monocromático (Manus-style). Removidos todos os ícones coloridos, `CheckCircle2` verde, `BrainCircuit`, `Sparkles`, `Loader2`, `shimmer-text`, `border-breathe`, `ring-pulse`, `success-flash`, `thought-glow`. Substituídos por: indicadores geométricos (`✓`, `·`, `▌`), fonte monospace, borda esquerda fina como indicador de estado, cursor `▌` piscante no step ativo, fundo `#0a0a0b`, header lowercase `agente · pensando` / `agente · concluído em Ns`. Thoughts indentados com fonte menor e itálico dim. Interface idêntica (mesmas props) — ArccoChat sem alterações estruturais.
2. **src/index.css** — Adicionada animação `@keyframes cursor-blink` e `.animate-cursor-blink` (1s step-end infinite) para o indicador `▌`.
3. **pages/ArccoChat.tsx** — Substituído o loader orbitante (3 dots coloridos + shimmer-text) antes do primeiro step pelo mesmo estilo terminal inline: `agente · pensando▌`.

### Por quê:
Usuário pediu UI agentic/clean no estilo Manus — sem ícones coloridos, sem animações chamativas, visual profissional e minimalista.

---

## 2026-03-19 (10) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/tools/__init__.py` (novo)
- `backend/tools/catalog.py` (novo)
- `backend/tools/README.md` (novo)
- `backend/api/tools.py` (novo)
- `backend/main.py`
- `pages/ToolsStorePage.tsx`

### O que foi feito:
1. **backend/tools/catalog.py** — Fonte da verdade das tools. Lista `TOOLS_CATALOG` com 14 tools (dicts com id, name, description, category, status, icon_name, color). Helpers `get_tool_by_id()` e `get_available_tools()`.
2. **backend/tools/README.md** — Guia completo de integração: passo a passo (5 passos), checklist, convenções, tabela de categorias, paleta de cores, tabela de ícones. Qualquer IA ou dev consegue adicionar uma tool seguindo o guia.
3. **backend/api/tools.py** — `GET /api/agent/tools` (lista completa) e `GET /api/agent/tools/{tool_id}` (tool por ID).
4. **backend/main.py** — Registrou `tools_api` router com prefix `/api/agent`.
5. **pages/ToolsStorePage.tsx** — Agora busca catálogo de `/api/agent/tools` ao montar. `icon_name` (string) é resolvido para componente Lucide via `ICON_MAP`. Mantém fallback local se API falhar. Indicador de loading no header.

### Por quê:
Criar estrutura centralizada no backend (VPS) para o catálogo de tools, com guia para que qualquer IA saiba como integrar uma nova tool sem precisar perguntar.

---

## 2026-03-19 (9) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/ToolsStorePage.tsx` (novo)
- `pages/MyToolsPage.tsx` (novo)
- `App.tsx`

### O que foi feito:
1. **ToolsStorePage.tsx** — Tela Loja de Tools com 14 tools catalogadas (Pesquisa, Código, Documentos, Automação, Análise, Em breve). Filtros por categoria, busca por texto, botão Adicionar/Remover. Seleção persiste em `localStorage` (chave `arcco_selected_tools`).
2. **MyToolsPage.tsx** — Tela Minhas Tools mostrando apenas as tools que o usuário adicionou. Botão X para remover individualmente. Estado vazio com CTA para a Loja. Sincroniza com `localStorage` (evento `storage` para múltiplas abas).
3. **App.tsx** — Importou `ToolsStorePage` e `MyToolsPage`. Adicionou cases `TOOLS_STORE` e `TOOLS_MY` no `renderContent()`. `MyToolsPage` recebe `onNavigateToStore` para navegar diretamente para a Loja.

### Por quê:
Implementação das telas de Tools solicitadas pelo usuário. UI apenas — sem backend. Lógica de seleção simples via localStorage.

---

## 2026-03-19 (8) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/core/supabase_client.py`
- `backend/api/conversations.py`

### O que foi feito:
1. **supabase_client.py** — `query()` agora trata valores `None` nos filtros como `is.null` (PostgREST). Antes usava `eq.None` que não funciona.
2. **conversations.py** — GET `/conversations` sem `project_id` agora filtra `project_id=is.null`, retornando apenas conversas do chat normal. Com `project_id` continua filtrando pelo projeto específico.

### Por quê:
Recentes da sidebar não deve exibir conversas de projetos. Conversas de projeto só aparecem ao clicar no projeto.

---

## 2026-03-19 (7) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `App.tsx`
- `components/Sidebar.tsx`
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **App.tsx** — `handleNewInteraction` agora limpa `selectedProjectId` e `activeProject` antes de abrir nova sessão. Clicar em "Nova Interação" desvincula qualquer projeto ativo.
2. **Sidebar.tsx** — `loadSessions()` removeu todos os fallbacks de localStorage. Sem userId → array vazio. Com userId → somente `conversationApi.list(userId)`. `handleDeleteSession` não chama mais `chatStorage.deleteSession()`. Import de `chatStorage` removido (só `ChatSession` type permanece).
3. **ArccoChat.tsx** — `saveToSession()` virou no-op (backend já persiste via background task). Carregamento de sessão: se `chatSessionId` não for UUID → mensagens vazias (sem buscar localStorage). Import reduzido a só o type `Message`.

### Por quê:
Usuário pediu: histórico somente do Supabase, zero localStorage. "Nova Interação" deve fechar o projeto ativo e abrir chat limpo.

---

## 2026-03-19 (6) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/api/projects.py`
- `backend/api/conversations.py`
- `lib/projectApi.ts`
- `lib/conversationApi.ts`
- `App.tsx`
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **projects.py** — Adicionado `GET /projects/{id}` para buscar projeto por ID.
2. **conversations.py** — `GET /conversations` agora aceita `project_id` como query param opcional para filtrar conversas por projeto.
3. **projectApi.ts** — Adicionado método `get(projectId)`.
4. **conversationApi.ts** — `list()` aceita `projectId` opcional. Adicionado `findByProject(userId, projectId)`.
5. **App.tsx** — `useEffect` ao mudar `selectedProjectId`: carrega detalhes do projeto (`projectApi.get`), busca conversa existente do projeto (`findByProject`), carrega essa conversa ou inicia nova. Passa `project`, `onProjectUpdated`, `onProjectDeleted` para ArccoChatPage.
6. **ArccoChat.tsx** — Novas props `project`, `onProjectUpdated`, `onProjectDeleted`. Header exibe badge do projeto + botão de lápis. Greeting substitui por nome do projeto + trecho das instruções. Modal de edição completo: nome, instruções, lista de arquivos com delete, upload de novos arquivos, botão excluir projeto com confirmação dupla.

### Por quê:
Usuário pediu: chat se moldando ao projeto selecionado (1 conversa por projeto), botão de editar configurações do projeto (nome, instruções, arquivos, modelo), botão de excluir.

---

## 2026-03-19 (5) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `components/Sidebar.tsx`
- `lib/conversationApi.ts`
- `lib/preferencesApi.ts`
- `lib/projectApi.ts`

### O que foi feito:
1. **Sidebar.tsx** — Refatorou `useEffect` de histórico: extraiu lógica em `loadSessions()` e adicionou `setInterval(loadSessions, 15000)` para polling a cada 15s com ou sem userId. Antes, quando userId estava presente, carregava só uma vez e nunca atualizava.
2. **conversationApi.ts / preferencesApi.ts / projectApi.ts** — Corrigiu `API_BASE` de `http://localhost:8001/api/agent` para `/api/agent` (caminho relativo via Vite proxy). URL hardcoded quebraria em produção.

### Por quê:
Novas conversas criadas pelo chat não apareciam no histórico da Sidebar porque a lista era carregada apenas no mount. Polling de 15s garante que a Sidebar reflita conversas recentes sem precisar recarregar a página. URLs hardcoded corrigidas para funcionar em qualquer ambiente.

---

## 2026-03-19 (4) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/AdminPage.tsx`

### O que foi feito:
1. **AdminPage.tsx** — Adicionado `openai` no mapa `PROVIDER_ICONS` e no dropdown de providers do formulário de nova API key. Antes só existiam: `openrouter`, `anthropic`, `browserbase`, `browserbase_project_id`.

### Por quê:
Usuário não conseguia adicionar a chave da OpenAI pelo painel admin porque a opção "OpenAI" não existia no dropdown.

---

## 2026-03-19 (3) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados/criados:
- `migrations/004_pgvector.sql` *(criado)*
- `backend/services/embedding_service.py` *(criado)*
- `backend/services/project_rag_service.py` *(reescrito)*

### O que foi feito:
1. **004_pgvector.sql** — Migration para habilitar `pgvector`, dropar coluna `chunk_tsv` (FTS), adicionar `embedding vector(1536)`, criar índice HNSW (`vector_cosine_ops`, m=16, ef=64) e criar função RPC `search_project_chunks(p_project_id, p_embedding, p_top_k)` que retorna `chunk_text` + `similarity` ordenados por distância coseno.
2. **embedding_service.py** — Novo serviço. `get_embedding(text)` e `get_embeddings_batch(texts)` chamam OpenAI API (`text-embedding-3-small`, 1536 dims) via httpx. API key buscada da tabela `ApiKeys` (provider='openai') com fallback para env var `OPENAI_API_KEY`. Cache da key em memória.
3. **project_rag_service.py** — Reescrito. `insert_chunks_for_file()` agora gera embeddings em batch (100/chamada) e insere com coluna `embedding`. `search_project_context()` gera embedding da query e chama RPC `search_project_chunks` via `db.rpc()`. FTS removido completamente.

### Por quê:
Usuário solicitou migração de FTS (keyword search) para pgvector (busca semântica por similaridade), que é a abordagem usada em produção (inclusive pela Anthropic no Claude). pgvector encontra contexto por significado mesmo quando palavras exatas não batem, e usa menos tokens pois retorna chunks mais precisos.

---

## 2026-03-19 (2) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `components/Sidebar.tsx`
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **Sidebar.tsx** — `handleCreateProject()` agora faz upload dos arquivos selecionados para o backend via `projectApi.uploadFile()` após criar o projeto. Adicionado spinner de loading + status de upload no modal. Histórico agora carrega do Supabase como fonte principal (fallback localStorage). `handleDeleteSession` remove visualmente sem reload.
2. **ArccoChat.tsx** — ao clicar em conversa do histórico: detecta UUID (Supabase) vs timestamp (localStorage) e carrega mensagens da fonte correta.

### Por quê:
Arquivos do popup de projeto não estavam chegando ao backend (apenas no estado local React). RAG de projetos agora funciona de fato. Histórico do sidebar agora vem do Supabase.

---

## 2026-03-19 — Claude Code (claude-sonnet-4-6)

### Arquivos modificados/criados:
- `migrations/003_history_projects_preferences_memory.sql` *(criado)*
- `backend/core/supabase_client.py` *(modificado — métodos insert/update/upsert/delete/insert_many/rpc + fix upsert on_conflict)*
- `backend/models/schemas.py` *(modificado — novos schemas Conversation/Message/Project/Preferences, extended ChatRequest)*
- `backend/api/preferences.py` *(criado)*
- `backend/api/conversations.py` *(criado)*
- `backend/api/projects.py` *(criado)*
- `backend/api/chat.py` *(reescrito — injeção de contexto + conversation_id SSE + background task memória)*
- `backend/services/project_file_service.py` *(criado)*
- `backend/services/project_rag_service.py` *(criado — FTS PostgreSQL)*
- `backend/services/memory_service.py` *(criado — gpt-4o-mini síntese)*
- `backend/main.py` *(modificado — 3 novos routers)*
- `lib/preferencesApi.ts` *(criado)*
- `lib/projectApi.ts` *(criado)*
- `lib/conversationApi.ts` *(criado)*
- `lib/api-client.ts` *(modificado — userId/projectId/conversationId no chat())*
- `components/SettingsModal.tsx` *(modificado — carrega/salva preferências via Supabase)*
- `components/Sidebar.tsx` *(modificado — projetos via backend, selectedProjectId, userId prop)*
- `App.tsx` *(modificado — userId/selectedProjectId states, passados para Sidebar e ArccoChat)*
- `pages/ArccoChat.tsx` *(modificado — userId/projectId props, conversationId state, captura SSE conversation_id)*

### O que foi feito:
1. **SQL migration** — 6 novas tabelas: projects, conversations, messages, project_files, project_file_chunks (FTS), user_preferences, user_memory.
2. **supabase_client.py** — 6 novos métodos CRUD + corrigido upsert (on_conflict como query param, não header Prefer).
3. **chat.py** — Injeta custom_instructions, memória e RAG antes de chamar o orquestrador; emite `conversation_id` como primeiro evento SSE; salva histórico + atualiza memória via asyncio.ensure_future.
4. **project_rag_service.py** — Busca FTS via PostgREST `wfts(portuguese)`, insere chunks em batches de 50.
5. **project_file_service.py** — Upload para bucket `project-files`, extração em background task, chunks indexados no FTS.
6. **memory_service.py** — gpt-4o-mini sintetiza fatos permanentes com limite rígido de 1500 chars.
7. **Frontend** — Sidebar conectado ao backend de projetos; SettingsModal carrega/salva preferências do Supabase; ArccoChat passa userId/projectId/conversationId na chamada de chat.

### Por quê:
Implementação completa da camada de persistência: histórico de conversas, projetos com RAG (FTS), preferências do usuário e memória acumulativa do usuário — tudo integrado ao Supabase.

---

## 2026-03-12 21:00 — Claude Code (Sonnet)

### Arquivos modificados:
- `backend/agents/executor.py`
- `backend/agents/orchestrator.py`
- `backend/core/llm.py`
- `backend/api/export.py`
- `backend/agents/prompts.py`

### O que foi feito:
1. **executor.py** — Moveu `from e2b_code_interpreter import Sandbox` para dentro de try/except ImportError. Corrigiu `execution_result.text or ""` (era None).
2. **orchestrator.py** — Adicionou `_PLANNER_ACTION_TO_TOOL` map e `tool_choice` forçado no Planner loop. Adicionou try/except em todas as execuções de tools. Removeu segunda chamada LLM na consolidação final (streaming direto de `message["content"]`). Corrigiu `accumulated_context` para incluir resultado real do browser.
3. **llm.py** — Adicionou parâmetro `tool_choice=None` em `call_openrouter()`.
4. **export.py** — Adicionou fallback reportlab quando Playwright indisponível para PDF.
5. **prompts.py** — Adicionou regras de formatação no CHAT_SYSTEM_PROMPT proibindo `**` e `#`.

### Por quê:
3 bugs críticos: E2B não executava, loop crashava na consolidação, browser agent não aparecia. PDF export falhava. Respostas vinham com markdown.

---

## 2026-03-13 08:30 — Claude Code (Sonnet)

### Arquivos modificados:
- `backend/agents/executor.py`

### O que foi feito:
1. **executor.py** — Reescreveu `_execute_python()` para API E2B v2.4.1: `Sandbox.create(api_key=...)` ao invés do construtor. Captura stdout de `result.logs.stdout` (print). Captura expressões de `result.text`. Sandbox destruído com `.kill()` no finally.

### Por quê:
E2B v2.4.1 mudou a API. `Sandbox(api_key=...)` dava erro. `result.text` era None para print(). Testado e confirmado funcionando com sandbox cloud.

---

## 2026-03-13 08:50 — Claude Code (Sonnet)

### Arquivos modificados:
- `backend/agents/prompts.py`
- `backend/agents/registry.py`
- `backend/agents/planner.py`
- `backend/agents/orchestrator.py`
- `backend/api/admin.py`

### O que foi feito:
1. **prompts.py** — Adicionou `PLANNER_SYSTEM_PROMPT` como constante separada.
2. **registry.py** — Adicionou agente `planner` (7o agente) com modelo `openai/gpt-4o-mini` e import do PLANNER_SYSTEM_PROMPT.
3. **planner.py** — Trocou prompt hardcoded por `registry.get_prompt("planner")`.
4. **orchestrator.py** — Trocou `supervisor_model` por `registry.get_model("planner")` na chamada do Planner.
5. **admin.py** — Adicionou `"planner": "PLANNER_SYSTEM_PROMPT"` em `_PROMPT_CONSTANTS`. Adicionou `"planner"` nos DEFAULTS do `reset_agent` com import.

### Por quê:
Planner usava o mesmo modelo caro do Supervisor (claude-3.5-sonnet). Agora usa modelo leve (gpt-4o-mini) editável pelo admin. Economia de tokens + velocidade. Planner visível no admin como 7o agente.

---

## 2026-03-13 09:15 — Claude Code (Sonnet)

### Arquivos modificados:
- `components/chat/TextDocCard.tsx`
- `components/chat/DocumentPreviewModal.tsx` (novo)
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **TextDocCard.tsx** — Redesenhado como card compacto. Removeu editor inline. Adicionou `onOpenPreview` callback e botão "Preview".
2. **DocumentPreviewModal.tsx** — Criado novo componente. Modal overlay com textarea editável para text_doc, iframe para PDF/Excel. Fullscreen toggle, ESC para fechar, contagem de palavras, botões DOCX/PDF no footer.
3. **ArccoChat.tsx** — Removeu side panel de 45%. Adicionou estado `modalPreview`. FilePreviewCard e TextDocCard agora abrem DocumentPreviewModal. Melhorou visual do FilePreviewCard. Chat ocupa 100% largura.

### Por quê:
Usuário pediu preview em popup ao invés de side panel, com ambiente mais textual para edição de documentos.

---

## 2026-03-13 10:00 — Claude Code (Sonnet)

### Arquivos modificados:
- `CLAUDE.md`

### O que foi feito:
1. **CLAUDE.md** — Reescrito completamente. Atualizado com 7 agentes, pipeline Planner→Supervisor, TOOL_MAP, dependências E2B/Browserbase, regras de edição.

### Por quê:
CLAUDE.md estava desatualizado (5 agentes, pipeline antigo). Qualquer IA que abrir o repo precisa do estado real.

---

## 2026-03-13 15:00 — Claude Code (Sonnet)

### Arquivos modificados:
- `pages/ArccoChat.tsx`
- `pages/LoginPage.tsx`
- `pages/RegisterPage.tsx`
- `pages/ArccoDrive.tsx`
- `pages/AdminPage.tsx`
- `components/Sidebar.tsx`
- `components/SettingsModal.tsx`
- `components/ui/DotGridBackground.tsx` (novo)
- `components/chat/AgentThoughtPanel.tsx`
- `components/chat/BrowserAgentCard.tsx`
- `components/chat/DocumentPreviewModal.tsx`
- `components/chat/TextDocCard.tsx`
- `backend/api/location.py` (novo)
- `backend/main.py`
- `src/index.css`
- `index.tsx`
- `App.tsx`

### O que foi feito:
1. **DotGridBackground.tsx** — Novo componente substituindo CircuitBackground. Grid de linhas estilo Vercel + 2 glows radiais com CSS vars.
2. **index.css** — CSS custom properties para 3 temas (`--bg-base`, `--dot-color`, `--glow-primary`, etc.) aplicados via `[data-theme]` no `<html>`.
3. **index.tsx** — Aplica tema salvo antes do React renderizar (sem flash).
4. **SettingsModal.tsx** — ThemePicker com 3 opções (Dark/Dim/Midnight), persiste em localStorage e aplica `data-theme`.
5. **ArccoChat.tsx** — Textarea com auto-resize (scrollHeight, máx 200px). Mode toggle movido para header. Logo inline ao lado do greeting. Pool de 10 sugestões rotativas por horário. Badge de clima/localização acima da saudação. Subtitle com cidade integrada.
6. **AgentThoughtPanel.tsx** — Estado concluído exibe pills compactos; "Concluído em Xs"; expandir ao clicar; reset ao iniciar nova execução.
7. **BrowserAgentCard.tsx** — Cursor mais suave (`duration-[180ms]`), viewport `h-60`, semáforos corretos por estado.
8. **DocumentPreviewModal.tsx** — Preview estilo documento (serif, bg escuro), footer com contador palavras/chars e botões Word/PDF com ícones coloridos.
9. **location.py** — Novo endpoint `GET /api/agent/location`. Proxy server-side para `ipwho.is` + `Open-Meteo`. Evita bloqueio Safari ITP.
10. **main.py** — Registrou `location_api.router` em `/api/agent`.

### Por quê:
Série de melhorias de UX solicitadas: background Vercel-style, sistema de temas, input auto-resize, saudação personalizada por horário/local, componentes do agente mais compactos. Localização via backend para contornar Safari ITP que bloqueava fetch direto para `ipwho.is`.
