import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.http_client import http_client_manager
from app.services.auth_service import AuthService
from app.services.provider_service import ProviderService

# Routers
from app.api.v1.router import router as v1_router
from app.api.admin.auth import router as admin_auth_router
from app.api.admin.dashboard import router as admin_dashboard_router
from app.api.admin.providers import router as admin_providers_router
from app.api.admin.credentials import router as admin_credentials_router
from app.api.admin.proxies import router as admin_proxies_router
from app.api.admin.models import router as admin_models_router
from app.api.admin.routes import router as admin_routes_router
from app.api.admin.fusion import router as admin_fusion_router
from app.api.admin.judges import router as admin_judges_router
from app.api.admin.keys import router as admin_keys_router
from app.api.admin.logs import router as admin_logs_router
from app.api.admin.settings import router as admin_settings_router
from app.api.admin.backup import router as admin_backup_router
from app.api.admin.modules import router as admin_modules_router
from app.api.ollama import router as ollama_router
from app.modules.loader import ModuleLoader

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSessionLocal() as db:
        await AuthService.init_admin_user(db)
        await ProviderService.seed_default_presets(db)
        ModuleLoader.scan_modules()
        await ModuleLoader.sync_with_db(db)
    yield
    # Shutdown: close all active HTTP connection pools
    await http_client_manager.close_all()

app = FastAPI(
    title="MyAIrouter - Universal AI API Router & Gateway",
    description="Universal self-hosted LLM gateway with Direct, Priority Fallback, and Model Fusion engines.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Mount Public OpenAI-compatible API
app.include_router(v1_router)
app.include_router(v1_router, prefix="/api")

# Mount Admin Management API
app.include_router(admin_auth_router, prefix="/api/admin")
app.include_router(admin_dashboard_router, prefix="/api/admin")
app.include_router(admin_providers_router, prefix="/api/admin")
app.include_router(admin_credentials_router, prefix="/api/admin")
app.include_router(admin_proxies_router, prefix="/api/admin")
app.include_router(admin_models_router, prefix="/api/admin")
app.include_router(admin_routes_router, prefix="/api/admin")
app.include_router(admin_fusion_router, prefix="/api/admin")
app.include_router(admin_judges_router, prefix="/api/admin")
app.include_router(admin_keys_router, prefix="/api/admin")
app.include_router(admin_logs_router, prefix="/api/admin")
app.include_router(admin_settings_router, prefix="/api/admin")
app.include_router(admin_backup_router, prefix="/api/admin")
app.include_router(admin_modules_router, prefix="/api/admin")

# Mount Ollama Compatibility API (/api/show, /api/tags, /api/version)
app.include_router(ollama_router, prefix="/api")

# Static frontend serving in production
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_frontend(full_path: str):
        if full_path.startswith("api") or full_path.startswith("v1") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Endpoint not found")
        file_path = frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(
            str(frontend_dist / "index.html"),
            headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"},
        )

    @app.api_route("/{full_path:path}", methods=["POST", "PUT", "DELETE", "PATCH"], include_in_schema=False)
    async def fallback_non_get(full_path: str):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Endpoint not found")
