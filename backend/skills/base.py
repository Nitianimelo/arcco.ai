"""
Contrato de uma Skill Dinâmica do Arcco.

Cada skill é um módulo Python em backend/skills/ que expõe:
  - SKILL_META: SkillMeta  — metadados para descoberta e LLM
  - execute(args: dict) -> Coroutine[str]  — lógica de execução

O loader descobre automaticamente todos os módulos neste diretório
que satisfaçam este contrato, sem necessidade de registro manual.
"""

from typing import TypedDict


class SkillMeta(TypedDict):
    id: str
    """Identificador único em snake_case. Ex: 'consultar_cnpj'.
    Este ID é usado como nome da tool no OpenAI function calling.
    Deve ser único entre todas as skills."""

    name: str
    """Nome de exibição legível. Ex: 'Consultar CNPJ'."""

    description: str
    """Descrição para o LLM entender QUANDO e COMO usar a skill.
    Seja específico: mencione o tipo de entrada esperada e o que retorna.
    Ex: 'Consulta dados cadastrais de empresa brasileira pelo CNPJ.
         Retorna razão social, situação, endereço, sócios e atividade principal.'"""

    parameters: dict
    """JSON Schema no formato OpenAI function parameters.
    Exemplo:
    {
        "type": "object",
        "properties": {
            "cnpj": {
                "type": "string",
                "description": "CNPJ com ou sem formatação"
            }
        },
        "required": ["cnpj"]
    }
    """

    keywords: list
    """Palavras-chave que disparam esta skill.
    Se o texto do usuário contiver qualquer uma delas, a skill é injetada.
    Se a lista estiver vazia, a skill é SEMPRE injetada (útil para skills universais).

    Exemplos:
    - consultar_cnpj:   ["cnpj", "empresa", "razão social", "receita federal"]
    - cotacao_moeda:    ["dólar", "euro", "câmbio", "cotação", "moeda", "usd", "brl"]
    - rastrear_correios: ["rastreio", "encomenda", "correios", "pacote", "sedex"]

    Dica: use termos que o usuário digita naturalmente, não termos técnicos.
    """
