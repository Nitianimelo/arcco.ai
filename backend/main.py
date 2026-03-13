"""
Arcco AI Backend — FastAPI Application.

Entry point para o backend Python.
Serve todos os endpoints que antes eram Netlify Functions.
Inclui: chat, search, files, ocr, admin.

Uso:
    uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload
"""

import os
import logging
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import get_config
from backend.api import chat, router as intent_router, search, files, ocr, admin
from backend.api import export as export_api
from backend.api import location as location_api
from backend.agents import registry

# ── Logging ───────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────

app = FastAPI(
    title="Arcco AI Backend",
    description="Backend Python para Arcco AI — chat, agentes, busca, geração de arquivos, OCR",
    version="2.0.0",
)

config = get_config()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────

# Todos sob /api/agent/ para compatibilidade com o frontend
app.include_router(chat.router, prefix="/api/agent", tags=["chat"])
app.include_router(intent_router.router, prefix="/api/agent", tags=["router"])
app.include_router(search.router, prefix="/api/agent", tags=["search"])
app.include_router(files.router, prefix="/api/agent", tags=["files"])
app.include_router(ocr.router, prefix="/api/agent", tags=["ocr"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(export_api.router, prefix="/api/agent", tags=["export"])
app.include_router(location_api.router, prefix="/api/agent", tags=["location"])

# ── Health Check ──────────────────────────────────────

app_start_time = datetime.now()


@app.get("/")
async def root():
    """Redireciona a raiz para a documentação interativa."""
    return RedirectResponse(url="/docs")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Evita erro 404 chato no navegador."""
    return {}

@app.get("/health")
async def health():
    uptime = int((datetime.now() - app_start_time).total_seconds())
    return {
        "status": "ok",
        "version": "2.0.0",
        "model": config.openrouter_model,
        "uptime_seconds": uptime,
    }


# ── Startup ───────────────────────────────────────────

@app.on_event("startup")
async def startup():
    print("[ARCCO] ========== BUILD_VERSION=2.1.0-debug ==========")
    print(f"[ARCCO] openrouter_api_key loaded: {bool(config.openrouter_api_key)}")
    print(f"[ARCCO] supabase_url: {config.supabase_url[:40] if config.supabase_url else 'EMPTY'}")
    logger.info("Arcco AI Backend starting...")

    is_valid, msg = config.validate()
    if not is_valid:
        logger.warning(f"Config warning: {msg}")

    config.workspace_path.mkdir(parents=True, exist_ok=True)

    # Inicializa registry de agentes (carrega defaults + overrides persistidos)
    registry.initialize()
    logger.info("Backend ready")


@app.on_event("shutdown")
async def shutdown():
    logger.info("Arcco AI Backend shutting down...")


# ── Dev Runner ────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8001")),
        reload=True,
        log_level="info",
    )
