Pipeline de Design do Arcco

Visão geral

O pipeline de design do Arcco foi organizado para separar:
- busca semântica de template
- preenchimento de conteúdo
- adaptação visual controlada
- render final

Isso evita dois extremos:
- HTML livre demais, que quebra layout
- template rígido demais, que não adapta ao pedido

Arquitetura

1. Catálogo de templates

Arquivo:
- [design_templates.json](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/data/design_templates.json)

Cada template registrado precisa declarar:
- `id`
- `family`
- `label`
- `template_file`
- `format`
- `canvas_preset`
- `category`
- `description`
- `tags`
- `requires_image`
- `default_image_query`
- `slots`

Famílias suportadas:
- `story`
- `feed`
- `a4`
- `slide`

2. Templates HTML

Pasta:
- [design_templates](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/services/design_templates)

Cada template é um HTML real, pronto para preview/render.

Contrato visual recomendado:
- `.container-base`
- classe de formato:
  - `.format-ig-post-square`
  - `.format-ig-post-portrait`
  - `.format-ig-story`
  - `.format-a4`
  - `.format-slide-16-9`
- wrappers semânticos quando fizer sentido:
  - `.content-shell`
  - `.content-copy`
  - `.content-media`

Tokens usados pelo renderer:
- `{{ title }}`
- `{{ hero_image_url }}`
- `{{ slots.nome_do_slot }}`

3. Seleção semântica

Arquivo:
- [design_template_registry.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/services/design_template_registry.py)

Responsabilidades:
- listar templates
- buscar template por `id`
- inferir `family`
- fazer scoring semântico por:
  - `format_hint`
  - `tags`
  - `category`
  - `description`
- decidir o modo:
  - `deterministic`
  - `guided`
  - `open`

Funções principais:
- `infer_template_family(...)`
- `pick_design_template(...)`
- `choose_design_route(...)`
- `build_slot_defaults(...)`
- `build_guided_design_contract(...)`

4. Skill de peça única

Arquivo:
- [static_design_generator.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/skills/static_design_generator.py)

Ela gera um `StaticDesignSpec` com:
- `template_family`
- `template_id`
- `template_label`
- `canvas_preset`
- `render_mode`
- `template_score`
- `slot_updates`
- `image_query`
- `image_url`
- `style_overrides`
- `allowed_edits`
- `optional_blocks`
- `locked_regions`

5. Skill de slides

Arquivo:
- [slide_generator.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/skills/slide_generator.py)

Ela gera um `SlideDeck` com:
- seleção de template
- modo de render
- slots globais
- contrato guiado
- lista de slides

6. Render final

Arquivo:
- [design_template_renderer.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/services/design_template_renderer.py)

Responsabilidades:
- ler o template HTML
- montar os `slots`
- resolver imagem via Unsplash
- substituir tokens
- renderizar peça única ou deck de slides

7. Orquestração

Arquivo:
- [orchestrator.py](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/agents/orchestrator.py)

Regra atual:
- se o payload vier com `render_mode=deterministic`, o sistema tenta render local
- se vier `guided` ou `open`, o payload estruturado segue para o `design_generator`

No caso de `guided`, o orquestrador envia o contrato visual junto do contexto:
- `style_overrides`
- `allowed_edits`
- `optional_blocks`
- `locked_regions`

Modos de render

1. `deterministic`

Uso:
- quando existe template com aderência alta

Comportamento:
- estrutura fixa
- o sistema só preenche `slots`
- ideal para produção, consistência e menor risco visual

2. `guided`

Uso:
- quando existe template bom, mas o pedido pede adaptação real

Comportamento:
- o template é a base
- o modelo pode alterar só o que o contrato permitir

Campos do contrato guiado:
- `style_overrides`
  - direção de paleta
  - modo tipográfico
  - tratamento de imagem
  - tratamento de fundo
  - mood
- `allowed_edits`
  - áreas que podem ser adaptadas
- `optional_blocks`
  - blocos que podem ser adicionados ou omitidos
- `locked_regions`
  - partes da estrutura que não podem ser quebradas

Objetivo:
- adaptar sem destruir o layout

3. `open`

Uso:
- quando o catálogo não tem aderência suficiente
- ou quando o usuário pede algo explicitamente fora do padrão

Comportamento:
- geração livre
- sem template obrigatório

Como o guided funciona

Guided não é “criar do zero”.

Guided significa:
- procurar template
- usar esse template como base
- preservar:
  - proporção
  - grade
  - ordem de leitura
  - regiões críticas
- adaptar:
  - copy
  - cores
  - intensidade visual
  - imagem
  - CTA
  - blocos opcionais

Resumo da decisão:
- `deterministic`: preencher
- `guided`: adaptar sobre trilhos
- `open`: criar livremente

Como adicionar um novo template

1. Criar o HTML em:
- [design_templates](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/services/design_templates)

2. Registrar no catálogo:
- [design_templates.json](/Users/nitianimelofreire/Library/Mobile%20Documents/com~apple~CloudDocs/Arquivos%20das%20empresas/Grupo%20Arcco%20/Projeto%20Arcco%20agent/arcco.ai.agentV1-master/backend/data/design_templates.json)

3. Declarar bons metadados:
- `tags`
- `category`
- `description`
- `slots`

4. Reusar slots existentes sempre que possível

Exemplos de slots comuns:
- `eyebrow`
- `headline`
- `subheadline`
- `cta`
- `hero_image`
- `quote`
- `author`
- `card_1`
- `card_2`
- `step_1`
- `step_2`
- `step_3`

5. Só adicionar novos slots se fizer sentido semântico real

Se adicionar novos slots:
- atualize `build_slot_defaults(...)`
- e, se necessário, `build_guided_design_contract(...)`

6. Validar

Rodar:
```bash
python3 -m compileall backend
git diff --check
```

Boas práticas

- Não injetar HTML completo no prompt do modelo
- Buscar template por metadados, não por markup
- Preferir slots semânticos a seletores CSS crus
- Não usar `guided` para reconstruir layout inteiro
- Não usar `open` quando o catálogo já resolve bem
- Manter `locked_regions` pequenas, claras e estáveis

Resumo operacional

Fluxo de peça única:
1. pedido do usuário
2. `static_design_generator`
3. escolha semântica de template
4. decisão `deterministic/guided/open`
5. render local ou `design_generator`

Fluxo de slides:
1. pedido do usuário
2. `slide_generator`
3. escolha semântica de template
4. decisão `deterministic/guided/open`
5. render local ou `design_generator`

Estado atual

Catálogo atual:
- `story`: 40 templates
- `feed`: 40 templates

Objetivo do desenho atual:
- preservar design
- evitar regressão visual
- permitir adaptação controlada
- manter caminho aberto para novos templates
