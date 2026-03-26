# backend/skills — Motor de Skills Dinâmicas do Arcco
#
# Cada arquivo .py nesta pasta (exceto base.py e loader.py) é uma skill.
# Para criar uma nova skill, copie o template abaixo:
#
#   SKILL_META = {
#       "id": "minha_skill",          # snake_case, único
#       "name": "Minha Skill",        # Display name
#       "description": "...",         # Para o LLM saber quando usar
#       "parameters": {               # JSON Schema (OpenAI format)
#           "type": "object",
#           "properties": {
#               "param": {"type": "string", "description": "..."}
#           },
#           "required": ["param"]
#       }
#   }
#
#   async def execute(args: dict) -> str:
#       # Lógica da skill aqui
#       return "resultado como string"
#
# Após criar o arquivo, reinicie o backend. A skill será descoberta automaticamente.
