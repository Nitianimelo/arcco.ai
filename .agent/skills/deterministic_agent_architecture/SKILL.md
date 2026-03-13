---
name: "Deterministic Agent Architecture"
description: "Orientações para criar um fluxo de orquestração de agente baseado em tasks e fluxos determinísticos a fim de ter agentes mais rápidos, eficientes e que consomem menos tokens."
---

# Especificação Técnica: Arquitetura de Agente com Execução Determinística

## Stack Atual
- **Frontend/Functions**: Netlify (Netlify Functions)
- **Backend/DB**: Supabase (PostgreSQL + Edge Functions)
- **LLM**: API Anthropic (Claude)
- **Web Search**: Tavily API
- **Geração de arquivos**: PDF (já implementado)

---

## 1. Conceito Central

O agente opera em dois modos distintos:

| Modo | Quando | Usa LLM? | Custo de tokens |
|------|--------|----------|-----------------|
| **Determinístico** | A ação tem input/output previsível | Não | Zero |
| **Raciocínio** | Requer interpretação, síntese, decisão | Sim (contexto mínimo) | Mínimo necessário |

**Regra de ouro**: O LLM nunca executa. Ele planeja. A execução é sempre código.

---

## 2. Arquitetura de Fluxo

```
[Usuário envia mensagem]
        │
        ▼
┌──────────────────┐
│   ROUTER (leve)  │ ← Classifica intent + extrai parâmetros
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
[DETER.]  [COMPLEXO]
    │         │
    │         ▼
    │   ┌───────────┐
    │   │ PLANNER   │ ← LLM gera plano JSON estruturado
    │   └─────┬─────┘
    │         │
    │         ▼
    │   ┌───────────┐
    │   │ EXECUTOR  │ ← Itera steps: determinísticos = código, reasoning = LLM
    │   └─────┬─────┘
    │         │
    ▼         ▼
┌──────────────────┐
│   RESPOSTA FINAL │ ← Formata e retorna ao usuário
└──────────────────┘
```

---

## 3. Banco de Dados — Tabelas Supabase

### 3.1 `intent_actions` — Mapa de ações determinísticas

```sql
CREATE TABLE intent_actions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  intent_key TEXT UNIQUE NOT NULL,        -- ex: "web_search", "generate_pdf", "summarize_url"
  description TEXT,                        -- descrição humana da intent
  action_type TEXT NOT NULL,               -- "deterministic" | "reasoning" | "hybrid"
  function_endpoint TEXT,                  -- endpoint da Netlify/Edge Function que executa
  required_params JSONB DEFAULT '[]',      -- parâmetros obrigatórios extraídos do input
  optional_params JSONB DEFAULT '[]',      -- parâmetros opcionais
  prompt_template TEXT,                    -- template de prompt (só para hybrid/reasoning)
  max_tokens INTEGER DEFAULT 500,          -- limite de tokens se usar LLM
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Exemplos de intents pré-cadastradas:
INSERT INTO intent_actions (intent_key, description, action_type, function_endpoint, required_params) VALUES
('web_search', 'Busca na web via Tavily', 'deterministic', '/api/actions/web-search', '["query"]'),
('generate_pdf', 'Gera PDF a partir de conteúdo', 'deterministic', '/api/actions/generate-pdf', '["content", "title"]'),
('summarize_text', 'Resume texto longo', 'reasoning', '/api/actions/llm-call', '["text"]'),
('translate', 'Traduz texto', 'reasoning', '/api/actions/llm-call', '["text", "target_language"]'),
('general_chat', 'Conversa geral / pergunta aberta', 'reasoning', '/api/actions/llm-call', '["message"]'),
('analyze_and_report', 'Pesquisa + análise + PDF', 'hybrid', null, '["topic"]');
```

### 3.2 `task_runs` — Estado de execução (memória externalizada)

```sql
CREATE TABLE task_runs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  conversation_id UUID NOT NULL,           -- referência à conversa
  user_id UUID NOT NULL,
  intent_key TEXT NOT NULL,
  status TEXT DEFAULT 'pending',           -- pending | running | completed | failed
  plan JSONB,                              -- plano gerado pelo LLM (só para hybrid)
  steps JSONB DEFAULT '[]',                -- array de steps com resultados
  final_result TEXT,                       -- resultado final formatado
  tokens_used INTEGER DEFAULT 0,           -- controle de custo
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ
);

-- Índice para busca rápida
CREATE INDEX idx_task_runs_conversation ON task_runs(conversation_id);
CREATE INDEX idx_task_runs_status ON task_runs(status);
```

### 3.3 `conversation_context` — Contexto comprimido (substitui histórico no prompt)

```sql
CREATE TABLE conversation_context (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  conversation_id UUID UNIQUE NOT NULL,
  user_id UUID NOT NULL,
  summary TEXT,                            -- resumo comprimido da conversa até agora
  key_facts JSONB DEFAULT '[]',            -- fatos extraídos relevantes
  last_intent TEXT,                        -- última intent classificada
  turn_count INTEGER DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 4. Implementação dos Componentes

### 4.1 ROUTER — `netlify/functions/router.js`

O router é o primeiro ponto de contato. Ele classifica a mensagem e decide o caminho.

**Estratégia de classificação em 2 níveis:**

1. **Nível 1 — Regex/Keyword (zero tokens)**: Patterns óbvios são capturados sem LLM.
2. **Nível 2 — LLM micro-call (~50-80 tokens)**: Se nível 1 falha, faz um call mínimo.

```javascript
// netlify/functions/router.js

const KEYWORD_PATTERNS = {
  web_search: /\b(pesquis|busc|procur|encontr|search|google|internet)\w*/i,
  generate_pdf: /\b(gera|cri)\w*\s+(pdf|documento|relatório|report)/i,
  translate: /\b(traduz|translat)\w*/i,
};

export async function handler(event) {
  const { message, conversation_id, user_id } = JSON.parse(event.body);

  // NÍVEL 1: Keyword matching (zero tokens)
  let intent = matchKeywords(message);

  // NÍVEL 2: LLM micro-classification (só se nível 1 falhar)
  if (!intent) {
    intent = await classifyWithLLM(message);
  }

  // Busca a action no banco
  const action = await getIntentAction(intent);

  if (action.action_type === 'deterministic') {
    // Executa direto, sem LLM
    const params = await extractParams(message, action.required_params, intent);
    const result = await callFunction(action.function_endpoint, params);
    return formatResponse(result);
  }

  if (action.action_type === 'hybrid') {
    // Gera plano com LLM, executa steps
    return await executeHybridTask(message, action, conversation_id, user_id);
  }

  // Reasoning puro — chama LLM com contexto mínimo
  return await executeLLMCall(message, conversation_id, user_id);
}

function matchKeywords(message) {
  for (const [intent, pattern] of Object.entries(KEYWORD_PATTERNS)) {
    if (pattern.test(message)) return intent;
  }
  return null;
}

async function classifyWithLLM(message) {
  // PROMPT MÍNIMO — gasta ~50 tokens
  const response = await callClaude({
    max_tokens: 30,
    messages: [{
      role: 'user',
      content: `Classifique em UMA palavra-chave: web_search, generate_pdf, summarize_text, translate, analyze_and_report, general_chat.\n\nMensagem: "${message}"\n\nIntent:`
    }]
  });
  return response.content[0].text.trim().toLowerCase();
}
```

### 4.2 EXTRATOR DE PARÂMETROS — `extractParams()`

Para actions determinísticas, os parâmetros precisam ser extraídos da mensagem. Dois caminhos:

```javascript
async function extractParams(message, requiredParams, intent) {
  // Tentativa 1: Extração por padrão (zero tokens)
  if (intent === 'web_search') {
    // Remove o verbo de busca e usa o resto como query
    const query = message.replace(/\b(pesquis|busc|procur|encontr)\w*\s*(sobre|por|de|na web|na internet)?\s*/i, '').trim();
    if (query.length > 3) return { query };
  }

  if (intent === 'translate') {
    const langMatch = message.match(/(?:para|para o|em|to)\s+(inglês|english|espanhol|spanish|português|french|francês)/i);
    const text = message.replace(/traduz\w*.*?(?:para|to)\s+\w+\s*/i, '').trim();
    if (langMatch && text) return { text, target_language: langMatch[1] };
  }

  // Tentativa 2: LLM micro-extraction (~80 tokens)
  const response = await callClaude({
    max_tokens: 100,
    messages: [{
      role: 'user',
      content: `Extraia os parâmetros da mensagem como JSON.\nParâmetros necessários: ${JSON.stringify(requiredParams)}\nMensagem: "${message}"\nJSON:`
    }]
  });
  return JSON.parse(response.content[0].text.trim());
}
```

### 4.3 ACTIONS DETERMINÍSTICAS — Netlify Functions dedicadas

Cada action determinística é uma function isolada. Não toca no LLM.

#### `/api/actions/web-search.js`
```javascript
export async function handler(event) {
  const { query } = JSON.parse(event.body);

  const tavilyResponse = await fetch('https://api.tavily.com/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key: process.env.TAVILY_API_KEY,
      query,
      max_results: 5,
      search_depth: 'basic',
      include_answer: true,       // Tavily já retorna uma resposta sintetizada
      include_raw_content: false  // economiza payload
    })
  });

  const data = await tavilyResponse.json();

  // Formata resultado estruturado — SEM LLM
  return {
    statusCode: 200,
    body: JSON.stringify({
      answer: data.answer,          // resposta sintetizada do Tavily
      sources: data.results.map(r => ({
        title: r.title,
        url: r.url,
        snippet: r.content?.substring(0, 200)
      })),
      raw_for_context: data.answer  // guardado no Supabase para steps futuros
    })
  };
}
```

#### `/api/actions/generate-pdf.js`
```javascript
// Usa a lib que você já tem implementada
// Input estruturado, output determinístico
export async function handler(event) {
  const { content, title, format } = JSON.parse(event.body);

  const pdfBuffer = await generatePDF({ content, title, format });
  
  // Salva no Supabase Storage
  const { data } = await supabase.storage
    .from('generated-files')
    .upload(`pdfs/${Date.now()}-${title}.pdf`, pdfBuffer, {
      contentType: 'application/pdf'
    });

  return {
    statusCode: 200,
    body: JSON.stringify({
      file_url: data.publicUrl,
      message: `PDF "${title}" gerado com sucesso.`
    })
  };
}
```

### 4.4 PLANNER — Para tasks híbridas/complexas

Quando o router identifica uma task complexa, o Planner gera um plano JSON estruturado.

```javascript
async function executeHybridTask(message, action, conversation_id, user_id) {
  // 1. Busca contexto comprimido (não o histórico todo)
  const context = await getCompressedContext(conversation_id);

  // 2. LLM gera plano estruturado
  const plan = await callClaude({
    max_tokens: 300,
    system: `Você é um planejador de tarefas. Retorne APENAS um JSON válido sem markdown.
Cada step deve ter: "type" (deterministic|reasoning), "action" (nome da action), "params" (objeto).
Actions disponíveis: web_search, generate_pdf, summarize_text, format_response.
Minimize steps de reasoning. Prefira deterministic sempre que possível.`,
    messages: [{
      role: 'user',
      content: `Contexto da conversa: ${context?.summary || 'Nenhum'}\n\nPedido do usuário: "${message}"\n\nPlano JSON:`
    }]
  });

  const steps = JSON.parse(plan.content[0].text);

  // 3. Cria registro da task
  const taskRun = await createTaskRun(conversation_id, user_id, action.intent_key, steps);

  // 4. Executa steps sequencialmente
  const results = {};
  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];

    if (step.type === 'deterministic') {
      // Executa sem LLM
      const actionConfig = await getIntentAction(step.action);
      results[`step_${i}`] = await callFunction(actionConfig.function_endpoint, step.params);
    } else {
      // Reasoning — injeta só os resultados dos steps anteriores, não o histórico todo
      const stepContext = Object.entries(results)
        .map(([k, v]) => `${k}: ${JSON.stringify(v.raw_for_context || v).substring(0, 500)}`)
        .join('\n');

      results[`step_${i}`] = await callClaude({
        max_tokens: step.max_tokens || 500,
        messages: [{
          role: 'user',
          content: `${step.prompt || step.params.instruction}\n\nDados disponíveis:\n${stepContext}`
        }]
      });
    }

    // Grava resultado do step no Supabase
    await updateTaskStep(taskRun.id, i, results[`step_${i}`]);
  }

  // 5. Retorna último resultado como resposta
  return formatFinalResponse(results, steps);
}
```

### 4.5 CONTEXTO COMPRIMIDO — Substitui histórico no prompt

Em vez de enviar 20 mensagens anteriores no prompt (= milhares de tokens), mantemos um resumo comprimido no Supabase.

```javascript
// Roda após cada interação completada
async function updateCompressedContext(conversation_id, user_message, assistant_response) {
  const current = await getCompressedContext(conversation_id);

  if (current && current.turn_count < 5) {
    // Primeiros 5 turnos: append simples (barato)
    const newFact = extractKeyFact(user_message, assistant_response); // regex, não LLM
    await supabase.from('conversation_context').update({
      key_facts: [...current.key_facts, newFact],
      turn_count: current.turn_count + 1,
      updated_at: new Date().toISOString()
    }).eq('conversation_id', conversation_id);
  } else if (current && current.turn_count % 5 === 0) {
    // A cada 5 turnos: comprimi com LLM (~100 tokens)
    const summary = await callClaude({
      max_tokens: 150,
      messages: [{
        role: 'user',
        content: `Resuma em 2-3 frases o contexto desta conversa:\nResumo anterior: ${current.summary || 'Nenhum'}\nFatos recentes: ${JSON.stringify(current.key_facts)}\nResumo:`
      }]
    });

    await supabase.from('conversation_context').update({
      summary: summary.content[0].text,
      key_facts: [],  // reset após comprimir
      turn_count: current.turn_count + 1,
      updated_at: new Date().toISOString()
    }).eq('conversation_id', conversation_id);
  }
}
```

---

## 5. Prompt do Agente para Chamadas LLM

Quando o LLM é chamado (modo reasoning), usar este system prompt otimizado:

```
Você é um assistente eficiente. Responda de forma direta e concisa.

REGRAS:
- Nunca invente dados. Se não sabe, diga que não sabe.
- Use apenas os dados fornecidos no contexto.
- Respostas em português BR.
- Sem introduções ou conclusões genéricas.
- Máximo de {max_tokens} tokens.

CONTEXTO DA CONVERSA:
{compressed_context}

DADOS DISPONÍVEIS:
{step_results}
```

**Observações sobre o prompt:**
- Sem historinha, sem persona elaborada. Direto ao ponto = menos tokens gastos.
- `{compressed_context}` vem do Supabase, não do histórico de mensagens.
- `{step_results}` são outputs de steps determinísticos anteriores — já verificados, sem alucinação.

---

## 6. Fluxo de Resposta ao Usuário

```javascript
// Formata resposta final para o frontend
function formatFinalResponse(results, steps) {
  const lastStep = steps[steps.length - 1];
  const lastResult = results[`step_${steps.length - 1}`];

  // Se o último step foi determinístico, retorna direto
  if (lastStep.type === 'deterministic') {
    return {
      message: lastResult.message || lastResult.answer,
      sources: lastResult.sources || [],
      files: lastResult.file_url ? [lastResult.file_url] : [],
      tokens_used: 0
    };
  }

  // Se foi reasoning, retorna o texto gerado
  return {
    message: lastResult.content?.[0]?.text || lastResult,
    sources: collectSources(results),
    files: collectFiles(results),
    tokens_used: calculateTotalTokens(results)
  };
}
```

---

## 7. Métricas e Monitoramento

### Tabela `usage_metrics`

```sql
CREATE TABLE usage_metrics (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  conversation_id UUID NOT NULL,
  user_id UUID NOT NULL,
  intent_key TEXT NOT NULL,
  action_type TEXT NOT NULL,               -- deterministic | reasoning | hybrid
  tokens_input INTEGER DEFAULT 0,
  tokens_output INTEGER DEFAULT 0,
  execution_time_ms INTEGER,
  was_keyword_matched BOOLEAN DEFAULT false, -- se o router resolveu sem LLM
  created_at TIMESTAMPTZ DEFAULT now()
);

-- View para dashboard
CREATE VIEW usage_summary AS
SELECT
  intent_key,
  action_type,
  COUNT(*) as total_calls,
  AVG(tokens_input + tokens_output) as avg_tokens,
  SUM(CASE WHEN was_keyword_matched THEN 1 ELSE 0 END) as zero_token_calls,
  AVG(execution_time_ms) as avg_time_ms
FROM usage_metrics
WHERE created_at > now() - interval '7 days'
GROUP BY intent_key, action_type;
```

Isso te permite ver exatamente quanto está gastando por tipo de ação e otimizar o mapa de intents progressivamente.

---

## 8. Roadmap de Implementação

### Fase 1 — Fundação (1-2 semanas)
- [ ] Criar tabelas no Supabase (`intent_actions`, `task_runs`, `conversation_context`, `usage_metrics`)
- [ ] Implementar Router com keyword matching + classificação LLM
- [ ] Migrar web search existente para action determinística isolada
- [ ] Migrar geração de PDF para action determinística isolada
- [ ] Implementar sistema de métricas básico

### Fase 2 — Otimização (1-2 semanas)
- [ ] Implementar contexto comprimido (substituir histórico no prompt)
- [ ] Implementar Planner para tasks híbridas
- [ ] Implementar executor de steps sequenciais com estado no Supabase
- [ ] Refinar extração de parâmetros (menos calls ao LLM)

### Fase 3 — Escala (contínuo)
- [ ] Analisar métricas e converter mais intents para determinísticas
- [ ] Adicionar novas actions (gerar imagem, scraping, integração APIs)
- [ ] Implementar cache de respostas para queries repetidas
- [ ] A/B test de prompts para minimizar tokens em calls de reasoning

---

## 9. Estimativa de Economia de Tokens

| Cenário | Antes (tudo via LLM) | Depois (com router) | Economia |
|---------|---------------------|---------------------|----------|
| Web search simples | ~2000 tokens (prompt + historico + resposta) | ~80 tokens (classificação) ou 0 (keyword) | 96-100% |
| Gerar PDF | ~3000 tokens | ~80 tokens (classificação) + ~100 (extração params) | 94% |
| Pergunta com pesquisa + síntese | ~4000 tokens | ~80 (classificação) + ~300 (planner) + ~500 (síntese) | 78% |
| Chat geral | ~2000 tokens | ~80 (classificação) + ~800 (resposta com contexto comprimido) | 56% |

**Média estimada de economia: 70-80% de tokens em uso misto.**

---

## 10. Notas Técnicas

### Timeouts no Netlify
- Functions padrão: 10s (plano gratuito), 26s (plano pago)
- Para tasks híbridas longas: considerar migrar o executor para **Supabase Edge Functions** (timeout mais longo) ou usar **background functions** do Netlify (até 15 min, plano pago)

### Cache de Classificação
- Queries muito similares podem ser cacheadas no Supabase para evitar re-classificação
- Hash da mensagem normalizada → intent_key → TTL de 24h

### Fallback
- Se o router falhar ou o LLM retornar intent inválida, default para `general_chat`
- Se uma action determinística falhar, log no `task_runs` e retry uma vez antes de fallback para LLM

### Segurança
- Todas as functions devem validar `user_id` via Supabase Auth JWT
- Inputs sanitizados antes de qualquer execução
- Rate limiting por user_id na tabela de métricas
