"""
DefiniÃ§Ãµes de ferramentas por agente especialista.

Isolamento estrito: cada especialista tem acesso APENAS Ã s suas ferramentas.
  - Agente de Busca Web    â†’ WEB_SEARCH_TOOLS
  - Agente Gerador         â†’ FILE_GENERATOR_TOOLS
  - Agente de Design       â†’ [] (sem ferramentas â€” apenas geraÃ§Ã£o de JSON)
  - Agente Dev             â†’ [] (sem ferramentas â€” apenas geraÃ§Ã£o de cÃ³digo)
"""

# â”€â”€ Agente de Busca Web â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

# â”€â”€ Agente Gerador de Arquivos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
FILE_GENERATOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_pdf",
            "description": (
                "Gera um PDF profissional e retorna o link de download. "
                "MODO PLAYWRIGHT (recomendado para PDFs visuais): forneÃ§a 'html_content' com HTML completo e Tailwind CSS â€” o resultado visual Ã© infinitamente superior. "
                "MODO TEXTO (fallback): forneÃ§a 'title' + 'content' em markdown simples."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "TÃ­tulo do documento (usado no modo texto)"
                    },
                    "content": {
                        "type": "string",
                        "description": "ConteÃºdo em texto/markdown (usado no modo texto quando html_content nÃ£o Ã© fornecido)"
                    },
                    "html_content": {
                        "type": "string",
                        "description": (
                            "HTML completo com estilos Tailwind CSS embutidos para gerar um PDF visualmente rico. "
                            "Inclua <!DOCTYPE html>, <head> com <script src='https://cdn.tailwindcss.com'></script>, e todo o conteÃºdo no <body>. "
                            "Use classes Tailwind para cores, tipografia, tabelas, grids. Fundo branco, fonte sans-serif."
                        )
                    },
                    "filename": {
                        "type": "string",
                        "description": "Nome do arquivo sem extensÃ£o"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_pdf_template",
            "description": (
                "Gera um PDF usando um template HTML prÃ©-aprovado (Jinja2). "
                "O LLM fornece apenas os dados (JSON); o design profissional vem do template. "
                "Use para relatÃ³rios e propostas com visual padronizado e consistente."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "template_name": {
                        "type": "string",
                        "enum": ["relatorio", "proposta"],
                        "description": (
                            "'relatorio': RelatÃ³rio com KPIs, tabelas e seÃ§Ãµes. "
                            "'proposta': Proposta comercial com capa, entregas e investimento."
                        )
                    },
                    "data": {
                        "type": "object",
                        "description": (
                            "JSON com os dados para injetar no template. "
                            "Para 'relatorio': {titulo, subtitulo?, empresa?, data?, periodo?, resumo?, "
                            "metricas?: [{label, valor, variacao?, positivo?}], "
                            "secoes: [{titulo, texto?, tabela?: {colunas, linhas}, lista?}], conclusao?}. "
                            "Para 'proposta': {titulo, subtitulo?, empresa_origem?, empresa_destino?, data?, validade?, "
                            "contexto?, solucao?, "
                            "entregas?: [{titulo, descricao?}], "
                            "investimento?: {itens: [{servico, descricao?, valor}], total, condicoes?}, "
                            "proximos_passos?: [...], cta?, contato?, email?}."
                        )
                    },
                    "filename": {
                        "type": "string",
                        "description": "Nome do arquivo sem extensÃ£o"
                    }
                },
                "required": ["template_name", "data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_excel",
            "description": "Gera uma planilha Excel (.xlsx) com dados estruturados e retorna o link de download",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Nome da aba (mÃ¡ximo 31 caracteres)"
                    },
                    "headers": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "CabeÃ§alhos das colunas"
                    },
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },
                        "description": "Linhas de dados"
                    },
                    "filename": {
                        "type": "string",
                        "description": "Nome do arquivo (sem extensÃ£o)"
                    }
                },
                "required": [
                    "title",
                    "headers",
                    "rows"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_python",
            "description": "Executa Python para processar e formatar dados complexos. Use print() para output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "CÃ³digo Python a executar"
                    }
                },
                "required": [
                    "code"
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
            "description": "Delega a criaÃ§Ã£o de um documento bruto em texto para preview editÃ¡vel. O usuÃ¡rio exporta depois para DOCX ou PDF.",
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
            "description": "Abre um navegador headless para acessar, interagir e extrair conteÃºdo de um site. "
                           "Suporta aÃ§Ãµes como clicar em botÃµes, rolar a pÃ¡gina, digitar texto, e executar JavaScript. "
                           "Use quando precisar ler artigos completos, interagir com sites dinÃ¢micos (SPAs), passar por carrossÃ©is, "
                           "aceitar cookies, ou extrair dados de URLs que exigem renderizaÃ§Ã£o JavaScript.\n\n"
                           "TIPOS DE ACTIONS SUPORTADAS (no campo 'actions'):\n"
                           "- {\"type\": \"click\", \"selector\": \"CSS_SELECTOR\"} â€” Clica num elemento\n"
                           "- {\"type\": \"scroll\", \"direction\": \"down\", \"amount\": 500} â€” Rola a pÃ¡gina\n"
                           "- {\"type\": \"wait\", \"milliseconds\": 2000} â€” Espera X ms\n"
                           "- {\"type\": \"write\", \"text\": \"...\", \"selector\": \"CSS_SELECTOR\"} â€” Digita texto\n"
                           "- {\"type\": \"press\", \"key\": \"Enter\"} â€” Pressiona tecla\n"
                           "- {\"type\": \"screenshot\"} â€” Tira print da pÃ¡gina\n"
                           "- {\"type\": \"execute_javascript\", \"script\": \"...\"} â€” Executa JS customizado\n"
                           "- {\"type\": \"scrape\"} â€” Extrai o conteÃºdo apÃ³s as aÃ§Ãµes\n\n"
                           "EXEMPLO de carrossel: actions=[{\"type\":\"click\",\"selector\":\".next-slide\"},{\"type\":\"wait\",\"milliseconds\":1000},{\"type\":\"scrape\"}]",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL completa do site a ser acessado (ex: https://example.com/artigo)"
                    },
                    "actions": {
                        "type": "array",
                        "description": "Lista de aÃ§Ãµes a executar no browser ANTES de extrair o conteÃºdo. Cada aÃ§Ã£o Ã© um objeto com 'type' obrigatÃ³rio. Tipos: click, scroll, wait, write, press, screenshot, execute_javascript, scrape.",
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
                                    "description": "Seletor CSS do elemento (para click e write)"
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
                "Executa código Python para cálculos matemáticos, processamento de dados, "
                "formatação complexa, conversões ou qualquer lógica computacional. "
                "Use print() para exibir resultados. Timeout: 10 segundos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Código Python a executar. Use print() para output."
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
