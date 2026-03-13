> Para a documentação completa e atualizada do repositório, leia `/CLAUDE.md` na raiz do projeto.

# Arcco Multi-Agent Architecture (ReAct)

Este documento foi criado para que **qualquer Inteligência Artificial futura (ou desenvolvedor)** que leia este repositório consiga compreender imediatamente a arquitetura da orquestração de Agentes do Arcco.

## 1. Visão Geral (O Paradigma ReAct)
A arquitetura do Arcco (a partir de refatorações robustas na v2) abandonou o roteamento estático (onde um classificador escolhia 1 único agente para responder). O sistema agora baseia-se no padrão **ReAct (Reasoning and Acting)** com uma topologia de **Supervisor-Worker**.

O sistema possui um **Supervisor Central** que gerencia o fluxo da conversa, mantém a memória de curto prazo e decide quando acionar **Sub-agentes Especialistas (Workers)** através do uso de ferramentas nativas do modelo (*LLM Tool Calling / Function Calling*).

---

## 2. Componentes Principais

### O Coordenador (Supervisor)
- **Localização:** Definido no arquivo `registry.py` com o ID `"chat"`.
- **Missão:** É a única entidade que deve responder dialogando com o usuário final de forma humanizada.
- **Mecânica:** Ele carrega o `SUPERVISOR_SYSTEM_PROMPT` junto com a assinatura JSON de diversas ferramentas (`SUPERVISOR_TOOLS`). O LLM decide, de forma autônoma, se atende ao pedido via conversa orgânica ou se solicita a execução de uma etapa de processamento a um especialista.

### Os Especialistas (Sub-Agentes)
Não operam de forma isolada do usuário, eles operam como *Tool Workers*:
- **Web Search**: Consulta web, formata dados e fontes. Chamada pela função `ask_web_search`.
- **File Generator**: Compila PDFs/planilhas em branco usando dados providos via kwargs e devolve URLs. Chamada pela função `ask_file_generator`.
- **File Modifier**: Lê um link de PDF/XLS/PPT gerado ou fornecido, e injeta/substitui conteúdo alterando a base. Chamada pela função `ask_file_modifier`.
- **UI Designer (Arcco Builder)**: Especialista nativo em layout de Carrossel JSON format. Chamada pela função `generate_ui_design`.
- **Dev (Arcco Pages)**: Especialista nativo na escrita de páginas HTML/CSS com Tailwind e scripts inline. Chamada pela função `generate_web_page`.

---

## 3. Lógicas Estruturais de Proteção (`orchestrator.py`)

Para que o Arcco fosse viável, rápido e à prova de falhas (funcional até com modelos "menores" como `gpt-4o-mini`), implementamos 3 grandes guardrails dentro de `orchestrate_and_stream`:

### A) Limite Anti-Loop Infinito (MAX_ITERATIONS)
O ciclo ReAct é perigoso porque o modelo pode entrar em loop chamando a mesma ferramenta infinitamente se perder seu encadeamento lógico. Temos um laço cravado com limite numérico absoluto (ex: `3`). Ao estourar sem concluir, o backend encerra retornando uma mensagem educada de erro ao usuário.

### B) Terminal Tools (Front-End Protection)
O Front-End do Arcco (especificamente o Builder/Pages) renderiza o JSON/HTML em tempo real enquanto o LLM gera, mas **pára de funcionar** se o LLM enviar conversa orgânica ("markdown") misturada no meio de chaves de código puro.
- **A Solução:** Ferramentas que geram artefatos brutos (`design` e `dev`) são consideradas **Terminal Tools**.
- **Comportamento:** Quando o Supervisor invoca uma Terminal Tool, o orquestrador despacha o pedido para o especialista usando _True Streaming_ (o LLM gera e envia o código já fatiado via Server Script Events `SSE` direto para a resposta HTTP do usuário), obtendo uma sensação visual de altíssima velocidade. Logo a seguir, aplica-se um comando de `break` instantâneo na thread do LLM Supervisor, evitando que ele recupere a palavra e "brote" lixo no final da tag HTML, blindando o front-end.

### C) Quality Assurance (QA Agent Loop)
Originalmente todos especialistas passavam por um Agente de QA síncrono que bloqueava a etapa visual em 2~3 segundos enquanto revisava a resposta atrás de quebra de regras.
Visando máxima performance anti-modelo:
- Para tarefas simples não terminais: O QA valida rapidamente e atua como injetor de feedback e Retry.
- Para tarefas "Terminal Tools" em streaming hiper-rápido: O QA é deslocado usando `asyncio.create_task` para validar o log silenciosamente em **background** (em paralelo), desatarraxando a validação visual.

---

## 4. Hot-Reload Dinâmico do Painel Administrativo

Diferente de sistemas que apenas leem de um banco de dados, o Painel Administrativo (`api/admin.py`) do Arcco **reescreve fisicamente o código fonte do Python**.

Quando o administrador altera algo na tela (GUI):
1. **Prompts Ocultos:** Usa Expressões Regulares (Regex multiline) para localizar as constantes dentro de `prompts.py` e sobreescrever todo o texto em disco rígido instantaneamente.
2. **Tools Paramétricas:** Transforma a estrutura da Web Tool em AST (Abstract Syntax Tree), manipula seu nó alvo seguro em `tools.py` injetando JSON, serializando em Python code limpo.
3. **Mágica:** O Uvicorn está em modo `--reload` em root. Ao sentir alteração de disco nos `.py`, recicla automaticamente a Workstation RAM em meio segundo.

### Se precisar editar prompts manualmente:
Não há problema, os arquivos são reais. Vá direto em `agents/prompts.py` ou `agents/tools.py`. O app será buildado mantendo a alteração que a sua versão do painel exibe e o script reconhecerá.
