"""
Definições de ferramentas por capability e especialista ativos.

Fonte de verdade prática:
- WEB_SEARCH_TOOLS
- FILE_MODIFIER_TOOLS
- TEXT_GENERATOR_TOOLS
- DESIGN_GENERATOR_TOOLS
- SUPERVISOR_TOOLS
"""

# Web search
WEB_SEARCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Pesquisa informaÃ§Ãµes atualizadas na internet",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Consulta de busca"
                    }
                },
                "required": [
                    "query"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "LÃª e extrai texto de uma URL especÃ­fica",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL para acessar"
                    }
                },
                "required": [
                    "url"
                ]
            }
        }
    }
]

# Geradores usados pela nova orquestraÃ§Ã£o de preview editÃ¡vel.
TEXT_GENERATOR_TOOLS = []
DESIGN_GENERATOR_TOOLS = []

# â”€â”€ Agente Modificador de Arquivos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
FILE_MODIFIER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_file_content",
            "description": "Baixa e lÃª a estrutura de um arquivo (PDF, Excel, PPTX) antes de modificar. Sempre chame isso primeiro.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL do arquivo a ser lido"
                    }
                },
                "required": [
                    "url"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_session_file",
            "description": "Lê o conteúdo já extraído de um arquivo anexado na sessão efêmera atual. Use query para buscar apenas trechos relevantes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "ID da sessão efêmera do chat"
                    },
                    "file_name": {
                        "type": "string",
                        "description": "Nome original do arquivo anexado na sessão"
                    },
                    "query": {
                        "type": "string",
                        "description": "Pergunta ou termos para localizar os trechos mais relevantes dentro do arquivo"
                    }
                },
                "required": [
                    "session_id",
                    "file_name"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modify_excel",
            "description": "Modifica uma planilha Excel (.xlsx) e retorna link de download",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL da planilha original"
                    },
                    "cell_updates": {
                        "type": "array",
                        "description": "CÃ©lulas a atualizar",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sheet": {
                                    "type": "string",
                                    "description": "Nome da aba (opcional, usa a primeira se omitido)"
                                },
                                "cell": {
                                    "type": "string",
                                    "description": "ReferÃªncia da cÃ©lula (ex: A1, B3)"
                                },
                                "value": {
                                    "type": "string",
                                    "description": "Novo valor"
                                }
                            },
                            "required": [
                                "cell",
                                "value"
                            ]
                        }
                    },
                    "append_rows": {
                        "type": "array",
                        "description": "Linhas a adicionar no final da aba",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sheet": {
                                    "type": "string",
                                    "description": "Nome da aba (opcional)"
                                },
                                "values": {
                                    "type": "array",
                                    "items": {
                                        "type": "string"
                                    },
                                    "description": "Valores da linha"
                                }
                            },
                            "required": [
                                "values"
                            ]
                        }
                    },
                    "output_filename": {
                        "type": "string",
                        "description": "Nome do arquivo modificado (sem extensÃ£o)"
                    }
                },
                "required": [
                    "url"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modify_pptx",
            "description": "Modifica uma apresentaÃ§Ã£o PowerPoint (.pptx) substituindo textos e retorna link de download",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL da apresentaÃ§Ã£o original"
                    },
                    "text_replacements": {
                        "type": "array",
                        "description": "SubstituiÃ§Ãµes de texto em todos os slides",
                        "items": {
                            "type": "object",
                            "properties": {
                                "find": {
                                    "type": "string",
                                    "description": "Texto a encontrar"
                                },
                                "replace": {
                                    "type": "string",
                                    "description": "Texto de substituiÃ§Ã£o"
                                }
                            },
                            "required": [
                                "find",
                                "replace"
                            ]
                        }
                    },
                    "output_filename": {
                        "type": "string",
                        "description": "Nome do arquivo modificado (sem extensÃ£o)"
                    }
                },
                "required": [
                    "url",
                    "text_replacements"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modify_pdf",
            "description": "Modifica um PDF existente (extrai texto, aplica alteraÃ§Ãµes, regera o documento) e retorna link de download",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL do PDF original"
                    },
                    "text_replacements": {
                        "type": "array",
                        "description": "SubstituiÃ§Ãµes de texto no documento",
                        "items": {
                            "type": "object",
                            "properties": {
                                "find": {
                                    "type": "string",
                                    "description": "Texto a encontrar"
                                },
                                "replace": {
                                    "type": "string",
                                    "description": "Texto de substituiÃ§Ã£o"
                                }
                            },
                            "required": [
                                "find",
                                "replace"
                            ]
                        }
                    },
                    "append_content": {
                        "type": "string",
                        "description": "ConteÃºdo adicional a inserir no final do documento"
                    },
                    "output_filename": {
                        "type": "string",
                        "description": "Nome do arquivo modificado (sem extensÃ£o)"
                    }
                },
                "required": [
                    "url"
                ]
            }
        }
    }
]

# â”€â”€ Agente Supervisor (Orquestrador) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
SUPERVISOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_session_file",
            "description": "Consulta um arquivo anexado na sessão efêmera do chat. Use esta ferramenta para ler ou buscar trechos do conteúdo extraído.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "ID da sessão efêmera do chat"
                    },
                    "file_name": {
                        "type": "string",
                        "description": "Nome original do arquivo anexado"
                    },
                    "query": {
                        "type": "string",
                        "description": "Pergunta ou palavras-chave para retornar apenas os trechos relevantes"
                    }
                },
                "required": [
                    "session_id",
                    "file_name"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_text_generator",
            "description": "Delega a criação de um documento oficial (Contratos, Relatórios, Artigos, Propostas, Manuais). Retorna o conteúdo formatado em Markdown rico (com títulos #, listas e negrito) para exportação perfeita em PDF/DOCX.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title_hint": {
                        "type": "string",
                        "description": "TÃ­tulo sugerido para o documento"
                    },
                    "instructions": {
                        "type": "string",
                        "description": "InstruÃ§Ãµes de estrutura, tom e objetivo do documento"
                    },
                    "content_brief": {
                        "type": "string",
                        "description": "Contexto, dados e pontos que devem aparecer no texto"
                    }
                },
                "required": [
                    "instructions",
                    "content_brief"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_design_generator",
            "description": "Delega a criaÃ§Ã£o de um design em HTML bonito para preview editÃ¡vel estilo canvas. O usuÃ¡rio exporta depois para PNG, JPEG, PDF ou PPTX.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title_hint": {
                        "type": "string",
                        "description": "TÃ­tulo sugerido para o design"
                    },
                    "instructions": {
                        "type": "string",
                        "description": "InstruÃ§Ãµes de layout, hierarquia visual e objetivo"
                    },
                    "content_brief": {
                        "type": "string",
                        "description": "Dados, textos e contexto a serem transformados em design"
                    },
                    "design_direction": {
                        "type": "string",
                        "description": "DireÃ§Ã£o visual opcional: editorial, premium, comercial, minimalista, etc."
                    }
                },
                "required": [
                    "instructions",
                    "content_brief"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_file_modifier",
            "description": "Delega a modificaÃ§Ã£o de um arquivo (PDF, Excel, PPTX) existente na conversa ou anexado na sessÃ£o para o Especialista. Retorna URL do novo arquivo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_url": {
                        "type": "string",
                        "description": "URL do arquivo original que precisa ser modificado"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "ID da sessÃ£o efÃªmera quando o arquivo estiver anexado no chat"
                    },
                    "file_name": {
                        "type": "string",
                        "description": "Nome original do arquivo anexado na sessÃ£o"
                    },
                    "instructions": {
                        "type": "string",
                        "description": "InstruÃ§Ãµes de modificaÃ§Ã£o (ex: 'Altere a cÃ©lula B2 para 100', 'Adicione nova linha no final')"
                    }
                },
                "required": [
                    "instructions"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_browser",
            "description": (
                "Abre um navegador remoto na Steel para acessar, interagir e extrair conteúdo de sites dinâmicos. "
                "Use quando o site exige JavaScript, SPA, login, cliques, scroll, formulários ou leitura de conteúdo que ask_web_search não consegue.\n\n"
                "O comportamento agora é ITERATIVO: o backend observa o estado atual da página, decide UMA micro-ação, executa, observa de novo e repete até concluir o objetivo. "
                "Não trate o campo 'actions' como roteiro cego obrigatório.\n\n"
                "CAMPO PRINCIPAL: passe o objetivo real no campo 'goal'. O sistema usa esse objetivo para dirigir a navegação.\n\n"
                "AUTO-HEALING: pop-ups simples, banners de cookies e overlays comuns são tratados automaticamente.\n\n"
                "HANDOFF HUMANO: se houver captcha, verificação humana ou bloqueio visual, a sessão será pausada para o usuário resolver e depois retomada da mesma página.\n\n"
                "MICRO-AÇÕES SUPORTADAS:\n"
                "- {\"type\": \"click\", \"selector\": \"text=Aceitar\"} — clica num elemento\n"
                "- {\"type\": \"scroll\", \"direction\": \"down\", \"amount\": 500} — rola a página\n"
                "- {\"type\": \"wait\", \"milliseconds\": 2000} — espera X ms\n"
                "- {\"type\": \"write\", \"text\": \"...\", \"selector\": \"#email\"} — digita texto\n"
                "- {\"type\": \"press\", \"key\": \"Enter\"} — pressiona tecla\n"
                "- {\"type\": \"screenshot\"} — tira print da página\n"
                "- {\"type\": \"execute_javascript\", \"script\": \"...\"} — executa JS customizado\n"
                "- {\"type\": \"scrape\"} — força extração textual se fizer sentido naquele momento\n\n"
                "ANTI-EXEMPLOS — O QUE NÃO FAZER:\n\n"
                "ERRADO: usar ask_browser para pesquisas no Google:\n"
                "  ask_browser(url='https://www.google.com/search?q=preço iphone')\n"
                "CORRETO: ask_web_search(query='preço iPhone 2026 Brasil')\n\n"
                "ERRADO: mandar 10 ações obrigatórias como se a web fosse determinística.\n"
                "CORRETO: goal='faça login e me diga o saldo exibido', com poucas ações opcionais só como pista.\n\n"
                "ERRADO: inventar seletores CSS desconhecidos:\n"
                "  {\"type\": \"click\", \"selector\": \"#btn-submit-8f3a2\"}\n"
                "CORRETO: {\"type\": \"click\", \"selector\": \"text=Enviar\"}\n\n"
                "ERRADO: usar ask_browser sem explicar o objetivo final.\n"
                "CORRETO: goal='abra o site, feche o modal e extraia o título exato da oferta principal'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL completa do site a ser acessado (ex: https://example.com/artigo)"
                    },
                    "goal": {
                        "type": "string",
                        "description": "Objetivo claro da navegação. Descreva o que deve ser encontrado, extraído ou concluído. Este é o principal guia do modo iterativo."
                    },
                    "actions": {
                        "type": "array",
                        "description": "Lista OPCIONAL de pistas iniciais de interação. O sistema não executa mais esse array cegamente como um roteiro fechado.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["click", "scroll", "wait", "write", "press", "screenshot", "execute_javascript", "scrape"],
                                    "description": "Tipo da aÃ§Ã£o"
                                },
                                "selector": {
                                    "type": "string",
                                    "description": "Seletor CSS ou de texto do elemento (para click, write e press). Use CSS como '#email', '.btn-submit' ou seletores de texto Playwright como 'text=\"Aceitar\"', 'text=\"Entrar\"' quando não souber a classe CSS exata — eles localizam pelo texto visível e são mais robustos."
                                },
                                "text": {
                                    "type": "string",
                                    "description": "Texto a digitar (para write)"
                                },
                                "key": {
                                    "type": "string",
                                    "description": "Tecla a pressionar (para press): Enter, Tab, Escape, etc."
                                },
                                "direction": {
                                    "type": "string",
                                    "enum": ["up", "down"],
                                    "description": "DireÃ§Ã£o do scroll"
                                },
                                "amount": {
                                    "type": "integer",
                                    "description": "Pixels para scroll"
                                },
                                "milliseconds": {
                                    "type": "integer",
                                    "description": "Milissegundos para wait"
                                },
                                "script": {
                                    "type": "string",
                                    "description": "CÃ³digo JavaScript a executar"
                                }
                            },
                            "required": ["type"]
                        }
                    },
                    "wait_for": {
                        "type": "integer",
                        "description": "Milissegundos para esperar antes de extrair conteÃºdo. Ãštil para SPAs que carregam via JavaScript. PadrÃ£o: sem espera."
                    },
                    "mobile": {
                        "type": "boolean",
                        "description": "Se true, acessa o site em modo mobile (viewport de celular). Ãštil para sites responsivos."
                    },
                    "include_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags HTML para incluir na extraÃ§Ã£o (ex: ['article', 'main']). Filtra o conteÃºdo."
                    },
                    "exclude_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags HTML para excluir da extraÃ§Ã£o (ex: ['nav', 'footer', 'aside']). Remove ruÃ­do."
                    },
                    "resume_token": {
                        "type": "string",
                        "description": "Token interno usado para retomar uma sessão pausada do navegador após handoff humano."
                    }
                },
                "required": [
                    "url"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_web_search",
            "description": (
                "Pesquisa rápida na internet via motor de busca (Tavily). "
                "Retorna resumo + fontes com links em < 2 segundos. "
                "Use para consultas factuais, notícias, preços, dados atualizados, documentação. "
                "Reserve ask_browser APENAS para sites que exigem JavaScript ou interação."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Consulta de busca otimizada (adicione ano 2026 para dados recentes)"
                    },
                    "fetch_url": {
                        "type": "string",
                        "description": "URL específica para ler o conteúdo completo (opcional). Use após avaliar os snippets da busca se precisar de mais detalhes de uma fonte."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_python",
            "description": (
                "Executa código Python em sandbox seguro (E2B) para cálculos, processamento de dados, "
                "conversões, geração de arquivos (Excel, CSV, gráficos PNG) e lógica computacional.\n\n"
                "REGRAS OBRIGATÓRIAS:\n"
                "- Use print() para exibir resultados — sem print(), o output NÃO aparece\n"
                "- Salve arquivos em /tmp/nome_arquivo.ext — o sistema os publica automaticamente\n"
                "- Timeout: 30 segundos por execução\n\n"
                "ANTI-EXEMPLOS — O QUE NÃO FAZER:\n\n"
                "ERRADO: omitir print() e esperar que o resultado apareça:\n"
                "  resultado = 2 + 2  — sem print(resultado), nada é exibido\n"
                "CORRETO: resultado = 2 + 2; print(resultado)\n\n"
                "ERRADO: usar caminhos de arquivo do sistema operacional local:\n"
                "  open('/Users/usuario/arquivo.csv', 'w')  — não existe no sandbox\n"
                "CORRETO: open('/tmp/arquivo.csv', 'w')\n\n"
                "ERRADO: tentar acessar a internet diretamente no código Python:\n"
                "  import requests; r = requests.get('https://api.exemplo.com/dados')\n"
                "CORRETO: use ask_web_search para buscar dados externos antes de execute_python\n\n"
                "ERRADO: usar execute_python para geração de texto narrativo ou documento:\n"
                "  execute_python(code=\"print('Relatório Anual:\\nA empresa cresceu 20%...')\")\n"
                "CORRETO: use ask_text_generator para documentos de texto\n\n"
                "ERRADO: gerar arquivo sem salvar em /tmp/:\n"
                "  import openpyxl; wb.save('planilha.xlsx')  — arquivo perdido fora do /tmp/\n"
                "CORRETO: wb.save('/tmp/planilha.xlsx')"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Código Python a executar. Use print() para output. Salve arquivos em /tmp/."
                    }
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deep_research",
            "description": (
                "Pesquisa profunda e autônoma em múltiplas etapas. Executa buscas paralelas, "
                "visita e analisa múltiplos sites, cruza informações e gera um relatório completo. "
                "Use para: pesquisa de mercado, análise competitiva, levantamento de dados de múltiplas fontes, "
                "comparativos, mapeamento de concorrentes, análise de setor/indústria. "
                "NÃO use para perguntas simples que ask_web_search resolve em 1 busca. "
                "Tempo médio: 60-180 segundos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Descrição detalhada do que pesquisar. Quanto mais específico, melhor o resultado. "
                            "Ex: 'Pesquisa de mercado de barbearias na Maraponga, Fortaleza-CE: "
                            "nomes, endereços, preços, avaliações Google, presença no Instagram'"
                        )
                    },
                    "context": {
                        "type": "string",
                        "description": "Contexto adicional: região geográfica, setor, tipo de dados desejados, objetivo da pesquisa"
                    }
                },
                "required": ["query"]
            }
        }
    },
]

# ── Tools do Arcco Computer (incluídas condicionalmente quando computer_enabled=True) ──

COMPUTER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_computer_files",
            "description": (
                "Lista os arquivos do usuário no Arcco Computer. "
                "Use para saber quais arquivos o usuário possui antes de ler ou manipular. "
                "Retorna id, nome, tipo, tamanho e data de cada arquivo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_path": {
                        "type": "string",
                        "description": "Caminho da pasta. '/' para raiz, '/Marketing' para subpasta. Default: '/'"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_computer_file",
            "description": (
                "Lê o conteúdo de um arquivo do Arcco Computer do usuário. "
                "Baixa e extrai texto de PDFs, DOCX, XLSX, imagens (OCR) e texto puro. "
                "Use o file_id obtido via list_computer_files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "ID do arquivo (obtido via list_computer_files)"
                    },
                    "query": {
                        "type": "string",
                        "description": "Pergunta ou termos para buscar trechos relevantes (opcional, ativa RAG)"
                    }
                },
                "required": ["file_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_computer_file",
            "description": (
                "Gerencia arquivos no Arcco Computer do usuário: mover para outra pasta, "
                "renomear, criar nova pasta ou salvar um novo arquivo gerado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["move", "rename", "create_folder", "save_new"],
                        "description": "Ação: move (mover arquivo), rename (renomear), create_folder (criar pasta), save_new (salvar novo arquivo)"
                    },
                    "file_id": {
                        "type": "string",
                        "description": "ID do arquivo (obrigatório para move e rename)"
                    },
                    "new_name": {
                        "type": "string",
                        "description": "Novo nome do arquivo (para rename)"
                    },
                    "target_folder": {
                        "type": "string",
                        "description": "Pasta destino. Ex: '/', '/Marketing', '/Docs' (para move, create_folder e save_new)"
                    },
                    "file_name": {
                        "type": "string",
                        "description": "Nome do novo arquivo (para save_new)"
                    },
                    "content": {
                        "type": "string",
                        "description": "Conteúdo do novo arquivo em texto ou HTML (para save_new)"
                    },
                    "file_type": {
                        "type": "string",
                        "description": "Tipo MIME do novo arquivo. Ex: text/plain, text/html, application/json (para save_new)"
                    }
                },
                "required": ["action"]
            }
        }
    },
]

# ── Spy Pages Tools (SimilarWeb via Apify) ───────────────────────────────────

SPY_PAGES_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "analyze_web_pages",
            "description": (
                "Analisa tráfego e métricas de sites usando dados do SimilarWeb via Apify. "
                "Retorna visitas mensais, bounce rate, tempo médio no site, páginas por visita, "
                "ranking global, top países de audiência, páginas mais visitadas e concorrentes. "
                "Use esta tool quando o usuário pedir para analisar, espiar ou comparar sites."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de URLs ou domínios para analisar. Máximo 4. Exemplos: ['google.com', 'https://facebook.com']"
                    }
                },
                "required": ["urls"]
            }
        }
    }
]
