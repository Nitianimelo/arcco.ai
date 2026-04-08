"""
Configuração centralizada do backend Arcco AI.
"""

import logging
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


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

    # Browser Agent (Steel)
    steel_api_key: str = ""
    e2b_api_key: str = ""

    # Apify (SimilarWeb Scraper)
    apify_api_key: str = ""

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

    # Admin panel credentials (must be supplied via env vars in production)
    admin_username: str = ""
    admin_password: str = ""

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
        )
        self.supabase_key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
            or os.getenv("SUPABASE_KEY", "")
            or os.getenv("VITE_SUPABASE_ANON_KEY", "")
        )
        self.supabase_storage_bucket = os.getenv("SUPABASE_STORAGE_BUCKET", self.supabase_storage_bucket)
        self.steel_api_key = (
            os.getenv("STEEL_API_KEY", "")
            or os.getenv("BROWSERBASE_API_KEY", "")
        )
        self.e2b_api_key = os.getenv("E2B_API_KEY", self.e2b_api_key)
        self.apify_api_key = os.getenv("APIFY_API_KEY", self.apify_api_key)
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
        self.admin_username = os.getenv("ADMIN_USERNAME", self.admin_username)
        self.admin_password = os.getenv("ADMIN_PASSWORD", self.admin_password)
        self.workspace_path = Path(os.getenv("AGENT_WORKSPACE", "/tmp/agent_workspace"))
        self.log_level = os.getenv("LOG_LEVEL", self.log_level)

        # Nota: _load_keys_from_supabase() é chamado explicitamente no startup
        # do FastAPI (main.py) via asyncio.to_thread(), para não bloquear o event loop.

    def _load_keys_from_supabase(self):
        """Busca API keys da tabela ApiKeys no Supabase para preencher chaves faltantes."""
        # Only try if we have Supabase credentials and are missing keys
        if not self.supabase_url or not self.supabase_key:
            logger.warning("[CONFIG] SUPABASE_URL/SUPABASE_KEY ausentes; fallback de chaves via Supabase desabilitado.")
            return

        needs_openrouter = not self.openrouter_api_key
        needs_anthropic = not self.api_key
        needs_steel = not self.steel_api_key
        needs_e2b = not self.e2b_api_key
        needs_apify = not self.apify_api_key

        if not (needs_openrouter or needs_anthropic
                or needs_steel
                or needs_e2b or needs_apify):
            logger.info("[CONFIG] All API keys loaded from environment variables.")
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
                        logger.warning("[CONFIG] Supabase ApiKeys query failed: status=%s", response.status_code)
                        rows = []
                    else:
                        rows = response.json()
            except Exception as e:
                logger.warning("[CONFIG] Supabase ApiKeys query error: %s", e)
                rows = []

            if rows:
                # Map provider -> api_key
                key_map = {
                    str(row.get("provider") or "").strip().lower(): row["api_key"]
                    for row in rows
                    if row.get("api_key") and row.get("provider")
                }
                logger.info("[CONFIG] Loaded API providers from Supabase: %s", sorted(key_map.keys()))

                if needs_openrouter and key_map.get("openrouter"):
                    self.openrouter_api_key = key_map["openrouter"]
                    logger.info("[CONFIG] OpenRouter API key loaded from Supabase.")

                if needs_anthropic and key_map.get("anthropic"):
                    self.api_key = key_map["anthropic"]
                    logger.info("[CONFIG] Anthropic API key loaded from Supabase.")

                steel_key = key_map.get("steel") or key_map.get("browserbase")
                if needs_steel and steel_key:
                    self.steel_api_key = steel_key
                    logger.info("[CONFIG] Steel API key loaded from Supabase.")

                e2b_key = key_map.get("e2b") or key_map.get("e2b_api_key")
                if needs_e2b and e2b_key:
                    self.e2b_api_key = e2b_key
                    logger.info("[CONFIG] E2B API key loaded from Supabase.")

                if needs_apify and key_map.get("apify"):
                    self.apify_api_key = key_map["apify"]
                    logger.info("[CONFIG] Apify API key loaded from Supabase.")

            if not self.openrouter_api_key and not self.api_key:
                logger.warning("[CONFIG] No LLM API key found (env or Supabase). Agent will fail.")
            else:
                logger.info("[CONFIG] API keys ready (env + Supabase fallback).")

            # Verificação explícita do Steel
            if not self.steel_api_key:
                logger.warning(
                    "[CONFIG] STEEL_API_KEY não configurada. Browser Agent ficará indisponível."
                )
            else:
                logger.info("[CONFIG] Steel credentials loaded.")
            if not self.e2b_api_key:
                logger.warning(
                    "[CONFIG] E2B_API_KEY não configurada. Execução Python via E2B ficará indisponível."
                )
            else:
                logger.info("[CONFIG] E2B credentials loaded.")

        except Exception as e:
            logger.warning("[CONFIG] Could not load API keys from Supabase: %s", e)

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
