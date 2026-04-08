# Capability Catalog

## Objetivo
Catálogo legível por humano/IA das capabilities do backend.

## Capabilities principais

### `session_file_read`
- Kind: `tool`
- Tool: `read_session_file`
- Route: `session_file`
- Output: `session_file_result`
- Terminal: `no`

### `web_search`
- Kind: `tool`
- Tool: `ask_web_search`
- Route: `web_search`
- Output: `search_result`
- Terminal: `no`

### `web_browse`
- Kind: `tool`
- Tool: `ask_browser`
- Route: `browser`
- Output: `browser_result`
- Terminal: `no`
- Handoff humano: `sim`

### `python_execute`
- Kind: `tool`
- Tool: `execute_python`
- Route: `python`
- Output: `python_result`
- Terminal: `no`

### `file_modify`
- Kind: `specialist`
- Tool: `ask_file_modifier`
- Route: `file_modifier`
- Output: `file_artifact`
- Terminal: `no` no runtime atual

### `text_document_generate`
- Kind: `specialist`
- Tool: `ask_text_generator`
- Route: `text_generator`
- Output: `file_artifact`
- Terminal: `sim`

### `design_generate`
- Kind: `specialist`
- Tool: `ask_design_generator`
- Route: `design_generator`
- Output: `design_artifact`
- Terminal: `sim`

### `deep_research`
- Kind: `specialist`
- Tool: `deep_research`
- Route: `deep_research`
- Output: `research_report`
- Terminal: `no`

## Skills atuais
- `slide_generator`
- `static_design_generator`
- `multi_doc_investigator`
- `web_form_operator`
- `local_lead_extractor`

## Observação
O runtime atual ainda possui regras especiais no `orchestrator.py`. Este catálogo descreve a intenção arquitetural e deve guiar futuras refatorações.
