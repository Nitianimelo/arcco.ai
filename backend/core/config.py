"""
Configuração centralizada do backend Arcco AI.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class AgentConfig:
    """Configuração centralizada."""

    # Anthropic
    api_key: str = ""
    model: str = ""
    model_haiku: str = "claude-haiku-4-5-20251001"
    model_opus: str = "claude-opus-4-6"
    max_tokens: int = 8096
    max_iterations: int = 20

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-3.5-sonnet"

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_storage_bucket: str = "chat-uploads"

    # Browser Agent (Browserbase)
    browserbase_api_key: str = ""
    browserbase_project_id: str = ""

    # Agent Behavior
    enable_caching: bool = True
    cache_ttl_seconds: int = 86400

    # Parser
    web_timeout: float = 20.0
    web_max_response_size: int = 2_000_000
    web_max_chars: int = 50_000

    # Streaming
    stream_enable: bool = True
    stream_chunk_size: int = 8

    # Workspace
    workspace_path: Path = field(default_factory=lambda: Path("/tmp/agent_workspace"))

    # Security
    allow_code_execution: bool = False
    max_code_timeout: float = 30.0

    # Deep Research
    deep_research_max_pages: int = 8
    deep_research_browser_concurrency: int = 3
    deep_research_timeout: int = 180

    # Logging
    log_level: str = "INFO"

    # CORS
    cors_origins: str = "*"

    def __post_init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", self.api_key)
        self.model = os.getenv("AGENT_MODEL", "claude-sonnet-4-5-20250929")
        self.max_tokens = int(os.getenv("AGENT_MAX_TOKENS", str(self.max_tokens)))
        self.max_iterations = int(os.getenv("AGENT_MAX_ITERATIONS", str(self.max_iterations)))
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", self.openrouter_api_key)
        self.openrouter_model = os.getenv("OPENROUTER_MODEL", self.openrouter_model)
        self.supabase_url = (
            os.getenv("SUPABASE_URL", "")
            or os.getenv("VITE_SUPABASE_URL", "")
            or "https://gfkycxdbbzczrwikhcpr.supabase.co"
        )
        self.supabase_key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
            or os.getenv("SUPABASE_KEY", "")
            or os.getenv("VITE_SUPABASE_ANON_KEY", "")
            or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imdma3ljeGRiYnpjenJ3aWtoY3ByIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTc4MjU5MywiZXhwIjoyMDg1MzU4NTkzfQ.zAB2HFhpyrtLD4aOvxDqS63Rvh_NwxgtS8ZhCj8xSnw"
        )
        self.supabase_storage_bucket = os.getenv("SUPABASE_STORAGE_BUCKET", self.supabase_storage_bucket)
        self.browserbase_api_key = os.getenv("BROWSERBASE_API_KEY", "")
        self.browserbase_project_id = os.getenv("BROWSERBASE_PROJECT_ID", "")
        self.enable_caching = os.getenv("AGENT_CACHE", "true").lower() == "true"
        self.cache_ttl_seconds = int(os.getenv("AGENT_CACHE_TTL", str(self.cache_ttl_seconds)))
        self.web_timeout = float(os.getenv("WEB_TIMEOUT", str(self.web_timeout)))
        self.web_max_response_size = int(os.getenv("WEB_MAX_SIZE", str(self.web_max_response_size)))
        self.web_max_chars = int(os.getenv("WEB_MAX_CHARS", str(self.web_max_chars)))
        self.allow_code_execution = os.getenv("ALLOW_CODE_EXEC", "false").lower() == "true"
        self.deep_research_max_pages = int(os.getenv("DEEP_RESEARCH_MAX_PAGES", str(self.deep_research_max_pages)))
        self.deep_research_browser_concurrency = int(os.getenv("DEEP_RESEARCH_CONCURRENCY", str(self.deep_research_browser_concurrency)))
        self.deep_research_timeout = int(os.getenv("DEEP_RESEARCH_TIMEOUT", str(self.deep_research_timeout)))
        self.cors_origins = os.getenv("CORS_ORIGINS", self.cors_origins)
        self.workspace_path = Path(os.getenv("AGENT_WORKSPACE", "/tmp/agent_workspace"))
        self.log_level = os.getenv("LOG_LEVEL", self.log_level)

        # Auto-load missing API keys from Supabase ApiKeys table
        self._load_keys_from_supabase()

    def _load_keys_from_supabase(self):
        """Busca API keys da tabela ApiKeys no Supabase para preencher chaves faltantes."""
        import logging
        logger = logging.getLogger(__name__)

        # Only try if we have Supabase credentials and are missing keys
        if not self.supabase_url or not self.supabase_key:
            return

        needs_openrouter = not self.openrouter_api_key
        needs_anthropic = not self.api_key
        needs_browserbase = not self.browserbase_api_key
        needs_browserbase_project = not self.browserbase_project_id

        if not (needs_openrouter or needs_anthropic
                or needs_browserbase or needs_browserbase_project):
            print("[CONFIG] All API keys loaded from environment variables")
            return

        try:
            import httpx
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
            }

            try:
                url = f"{self.supabase_url}/rest/v1/ApiKeys?select=provider,api_key&is_active=eq.true"
                with httpx.Client(timeout=10.0) as client:
                    response = client.get(url, headers=headers)
                    if response.status_code != 200:
                        print(f"[CONFIG] Supabase ApiKeys query failed: status={response.status_code}")
                        rows = []
                    else:
                        rows = response.json()
            except Exception as e:
                print(f"[CONFIG] Supabase ApiKeys query error: {e}")
                rows = []

            if rows:
                # Map provider -> api_key
                key_map = {row["provider"]: row["api_key"] for row in rows if row.get("api_key")}
                print(f"[CONFIG] Providers encontrados no Supabase: {list(key_map.keys())}")

                if needs_openrouter and key_map.get("openrouter"):
                    self.openrouter_api_key = key_map["openrouter"]
                    print(f"[CONFIG] OpenRouter API key loaded from Supabase: {self.openrouter_api_key[:15]}...")

                if needs_anthropic and key_map.get("anthropic"):
                    self.api_key = key_map["anthropic"]
                    print("[CONFIG] Anthropic API key loaded from Supabase")

                if needs_browserbase and key_map.get("browserbase"):
                    self.browserbase_api_key = key_map["browserbase"]
                    print("[CONFIG] Browserbase API key loaded from Supabase")

                if needs_browserbase_project and key_map.get("browserbase_project_id"):
                    self.browserbase_project_id = key_map["browserbase_project_id"]
                    print("[CONFIG] Browserbase Project ID loaded from Supabase")

            if not self.openrouter_api_key and not self.api_key:
                print("[CONFIG] WARNING: No LLM API key found (env or Supabase). Agent will fail.")
            else:
                print("[CONFIG] API keys ready (env + Supabase fallback)")

            # Verificação explícita do Browserbase
            if not self.browserbase_api_key:
                print("[CONFIG] WARNING: BROWSERBASE_API_KEY não configurada. "
                      "Browser Agent ficará indisponível. "
                      "Adicione provider='browserbase' na tabela ApiKeys do Supabase "
                      "ou defina BROWSERBASE_API_KEY como variável de ambiente.")
            if not self.browserbase_project_id:
                print("[CONFIG] WARNING: BROWSERBASE_PROJECT_ID não configurado. "
                      "Browser Agent ficará indisponível. "
                      "Adicione provider='browserbase_project_id' na tabela ApiKeys do Supabase "
                      "ou defina BROWSERBASE_PROJECT_ID como variável de ambiente.")
            if self.browserbase_api_key and self.browserbase_project_id:
                print(f"[CONFIG] Browserbase OK — key: {self.browserbase_api_key[:15]}... project: {self.browserbase_project_id[:15]}...")

        except Exception as e:
            print(f"[CONFIG] WARNING: Could not load API keys from Supabase: {e}")

    def validate(self) -> tuple[bool, str]:
        if not self.api_key and not self.openrouter_api_key:
            return False, "ANTHROPIC_API_KEY ou OPENROUTER_API_KEY necessário"
        if not self.supabase_url:
            return False, "SUPABASE_URL não configurada"
        if not self.supabase_key:
            return False, "SUPABASE_KEY não configurada"
        return True, "OK"



_config: Optional[AgentConfig] = None


def get_config() -> AgentConfig:
    global _config
    if _config is None:
        _config = AgentConfig()
    return _config


def reload_config() -> AgentConfig:
    global _config
    _config = None
    return get_config()
