# Tools do Arcco AI — Guia de Integração

> Este arquivo é o guia completo para adicionar novas tools à plataforma.
> Qualquer IA ou desenvolvedor que precisar adicionar uma tool DEVE seguir este guia.

---

## O que é uma Tool?

Uma **Tool** é uma capacidade especial que o agente Arcco pode usar durante uma conversa.
Exemplos: busca na web, execução de código Python, geração de PDF, controle de navegador.

Cada tool tem dois lados:
- **Backend** — a implementação Python que executa a lógica
- **Catálogo** — o registro que faz a tool aparecer na Loja do frontend

---

## Estrutura de Arquivos

```
backend/tools/
├── README.md          ← este guia (não editar a estrutura, só adicionar tools)
├── __init__.py        ← exporta TOOLS_CATALOG e get_tool_by_id
└── catalog.py         ← FONTE DA VERDADE — lista de todas as tools

backend/agents/
├── executor.py        ← implementação das tools que o agente usa
├── tools.py           ← definições JSON das tools para o LLM (function calling)
└── orchestrator.py    ← TOOL_MAP: mapeamento tool_name → função executora
```

---

## Como Adicionar uma Nova Tool — Passo a Passo

### Passo 1 — Registrar no Catálogo

Abra `backend/tools/catalog.py` e adicione um novo dicionário na lista `TOOLS_CATALOG`.

Escolha a categoria correta e coloque em ordem dentro dela:

```python
{
    "id": "minha_tool",             # snake_case, único, nunca mudar depois de publicar
    "name": "Minha Tool",           # nome de exibição no frontend
    "description": "Faz X e Y.",    # 1-2 linhas, sem markdown
    "category": "Automação",        # "Pesquisa" | "Código" | "Documentos" | "Automação" | "Análise" | "Em breve"
    "status": "available",          # "available" ou "coming_soon"
    "icon_name": "Zap",             # nome do ícone Lucide React (ver https://lucide.dev)
    "color": "from-violet-500/20 to-violet-600/10 border-violet-500/30",
                                    # padrão cinza para coming_soon: _COMING_SOON_COLOR
},
```

> Ao salvar `catalog.py`, o endpoint `GET /api/agent/tools` já retorna a nova tool automaticamente.
> Ela vai aparecer na Loja do frontend sem precisar alterar nenhum arquivo TypeScript.

---

### Passo 2 — Implementar a Tool no Executor

Abra `backend/agents/executor.py` e adicione a função que executa a tool:

```python
async def execute_minha_tool(session_id: str, params: dict) -> str:
    """
    Executa a Minha Tool.

    Params esperados pelo LLM:
      - param1 (str): descrição do param1
      - param2 (int, opcional): descrição do param2

    Retorna:
      String com o resultado formatado para o Supervisor.
    """
    param1 = params.get("param1", "")
    # ... sua lógica aqui ...
    result = f"Resultado: {param1}"
    return result
```

**Regra importante:** o executor NUNCA deve lançar exceções para fora.
Sempre faça try/except e retorne uma string de erro descritiva:

```python
async def execute_minha_tool(session_id: str, params: dict) -> str:
    try:
        # ... lógica ...
        return resultado
    except Exception as e:
        logger.error(f"[MINHA_TOOL] Erro: {e}")
        return f"Erro ao executar minha_tool: {str(e)}"
```

---

### Passo 3 — Definir o Schema JSON para o LLM

Abra `backend/agents/tools.py` e adicione a definição da tool no formato OpenAI function calling.

Encontre o array `SUPERVISOR_TOOLS` e adicione:

```python
{
    "type": "function",
    "function": {
        "name": "minha_tool",
        "description": "Descrição para o LLM de QUANDO usar esta tool e o que ela faz.",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "O que é param1 e como deve ser preenchido."
                },
                "param2": {
                    "type": "integer",
                    "description": "O que é param2 (opcional).",
                    "default": 10
                }
            },
            "required": ["param1"]
        }
    }
},
```

> A `description` é o que o LLM lê para decidir se vai usar a tool ou não.
> Seja específico sobre QUANDO usar e o que ela produz.

---

### Passo 4 — Registrar no TOOL_MAP do Orquestrador

Abra `backend/agents/orchestrator.py` e localize o dicionário `TOOL_MAP`.

Adicione a sua tool:

```python
TOOL_MAP = {
    # ... tools existentes ...
    "minha_tool": {
        "fn": executor.execute_minha_tool,
        "terminal": False,   # False = resultado volta ao Supervisor para continuar o loop
                             # True  = resultado vai direto para o frontend (stream finaliza)
    },
}
```

**Quando usar `terminal: True`?**
- A tool gera o output final (ex: gerador de documento, de apresentação)
- Não precisa de raciocínio adicional do Supervisor

**Quando usar `terminal: False`?**
- A tool retorna dados que o Supervisor precisa processar (ex: busca web, análise de arquivo)
- O Supervisor continua o loop ReAct com os dados

---

### Passo 5 (Opcional) — Criar um Serviço Separado

Se a lógica for complexa (mais de 50 linhas), crie um arquivo próprio em `backend/services/`:

```
backend/services/minha_tool_service.py
```

E importe no executor:

```python
from backend.services.minha_tool_service import processar_minha_tool

async def execute_minha_tool(session_id: str, params: dict) -> str:
    return await processar_minha_tool(params)
```

---

## Checklist Completo

Ao adicionar uma tool, marque cada item:

- [ ] `catalog.py` — tool registrada com todos os campos
- [ ] `executor.py` — função `execute_minha_tool()` implementada com try/except
- [ ] `tools.py` — schema JSON adicionado em `SUPERVISOR_TOOLS`
- [ ] `orchestrator.py` — tool adicionada no `TOOL_MAP`
- [ ] `AI_CHANGELOG.md` — registro da mudança feita

---

## Convenções Importantes

| Regra | Detalhe |
|---|---|
| IDs são permanentes | Nunca mude o `id` de uma tool após publicar — pode quebrar dados de usuários |
| Tool IDs = snake_case | Ex: `web_search`, `doc_generator`, `crm_integration` |
| coming_soon → available | Quando uma tool ficar pronta, mude apenas `status` de `"coming_soon"` para `"available"` |
| Sem LangChain/CrewAI | Toda lógica é Python puro + httpx + E2B + Browserbase |
| try/except no executor | O generator SSE não pode morrer por erro de tool |
| Serviços em `backend/services/` | Lógica complexa fora do executor |

---

## Categorias Disponíveis

| Categoria | Uso |
|---|---|
| `Pesquisa` | Tools que buscam informação externa (web, banco de dados) |
| `Código` | Tools que executam código ou scripts |
| `Documentos` | Tools que geram ou processam arquivos (PDF, Excel, PPTX) |
| `Automação` | Tools que controlam sistemas externos (browser, webhooks, APIs) |
| `Análise` | Tools que analisam dados e geram insights ou visualizações |
| `Em breve` | Tools planejadas mas não implementadas ainda |

---

## Ícones Disponíveis (exemplos comuns)

Consulte a lista completa em [lucide.dev](https://lucide.dev).

| icon_name | Visual |
|---|---|
| `Globe` | globo terrestre |
| `Code2` | `< />` |
| `Monitor` | tela de computador |
| `FileText` | documento |
| `BarChart3` | gráfico de barras |
| `Table2` | planilha |
| `Eye` | olho |
| `Mail` | envelope |
| `Database` | banco de dados |
| `Zap` | raio / lightning |
| `Image` | imagem |
| `Search` | lupa |
| `Bot` | robô |
| `Webhook` | webhook |
| `Presentation` | slides |
| `Calculator` | calculadora |
| `Calendar` | calendário |
| `MessageSquare` | balão de chat |

---

## Cores de Cartão — Paleta

Escolha uma cor que não esteja sendo usada para não ficar igual a outra tool:

```
Azul:     from-blue-500/20 to-blue-600/10 border-blue-500/30
Índigo:   from-indigo-500/20 to-indigo-600/10 border-indigo-500/30
Roxo:     from-purple-500/20 to-purple-600/10 border-purple-500/30
Violeta:  from-violet-500/20 to-violet-600/10 border-violet-500/30
Rosa:     from-pink-500/20 to-pink-600/10 border-pink-500/30
Vermelho: from-red-500/20 to-red-600/10 border-red-500/30
Laranja:  from-orange-500/20 to-orange-600/10 border-orange-500/30
Amarelo:  from-yellow-500/20 to-yellow-600/10 border-yellow-500/30
Verde:    from-green-500/20 to-green-600/10 border-green-500/30
Esmeralda:from-emerald-500/20 to-emerald-600/10 border-emerald-500/30
Teal:     from-teal-500/20 to-teal-600/10 border-teal-500/30
Ciano:    from-cyan-500/20 to-cyan-600/10 border-cyan-500/30
Cinza:    from-neutral-700/20 to-neutral-800/10 border-neutral-700/30  ← coming_soon
```

---

## Endpoint da API

O catálogo é exposto via:

```
GET /api/agent/tools
```

Retorna:
```json
[
  {
    "id": "web_search",
    "name": "Busca Web",
    "description": "...",
    "category": "Pesquisa",
    "status": "available",
    "icon_name": "Globe",
    "color": "from-blue-500/20 ..."
  },
  ...
]
```

O frontend (`pages/ToolsStorePage.tsx`) busca este endpoint ao montar e usa o catálogo retornado.
Se o endpoint falhar, usa uma lista de fallback hardcoded.
