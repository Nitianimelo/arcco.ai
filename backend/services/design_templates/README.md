Templates determinísticos de design

Estrutura:
- Cada template precisa existir em [backend/data/design_templates.json]
- Cada item do catálogo aponta para `template_file`
- O arquivo HTML correspondente vive nesta pasta

Contrato mínimo do catálogo:
- `id`
- `family`: `story` | `feed` | `a4` | `slide`
- `label`
- `template_file`
- `canvas_preset`
- `slots`

Contrato de preenchimento:
- O agente devolve `slot_updates` semânticos
- O renderer injeta esses slots no template
- Para templates com imagem, use `hero_image_url` no HTML e deixe o renderer resolver via Unsplash se necessário

Boas práticas:
- Use `.container-base` e as classes de formato do contrato visual
- Evite posicionar headline/CTA com coordenadas absolutas
- Prefira wrappers `.content-shell`, `.content-copy` e `.content-media`
- Para `slide`, uma seção por slide com `class="slide"`
