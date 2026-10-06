from typing import Optional, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_router_key_dep
from app.api.v1.router import list_models, retrieve_model
from app.models.entities import RouterApiKey
from app.models.entities import DiscoveredModel, RoutingProfile, RoutingCandidate, FusionProfile, Provider

router = APIRouter(tags=["Ollama Compatibility API"])

def _model_family(model_obj: DiscoveredModel) -> str:
    if "/" in model_obj.canonical_slug:
        return model_obj.canonical_slug.split("/")[0]
    return "custom"

@router.get("/version")
async def ollama_version():
    return {"version": "0.5.4"}

@router.post("/show")
async def ollama_show(request: Request, db: AsyncSession = Depends(get_db), router_key: Optional[RouterApiKey] = Depends(get_router_key_dep)):
    """
    Ollama-compatible /api/show endpoint for model inspection.
    Takes {"name": "model_name"} or {"model": "model_name"}.
    """
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})
    if not isinstance(body, dict):
        return JSONResponse(status_code=422, content={"error": "JSON object required"})
    model_name = body.get("name") or body.get("model") or ""
    if not isinstance(model_name, str):
        return JSONResponse(status_code=422, content={"error": "Model name must be a string"})
    model_name = model_name.strip()
    if not model_name:
        return JSONResponse(status_code=400, content={"error": "model name is required"})

    card = await retrieve_model(model_name, db, router_key)
    if isinstance(card, JSONResponse):
        return card
    model_name = card.id

    # Check routing profile
    slug = model_name.removeprefix("route/")
    r_res = await db.execute(
        select(RoutingProfile)
        .options(
            selectinload(RoutingProfile.candidates).selectinload(RoutingCandidate.model)
        )
        .where(RoutingProfile.slug == slug, RoutingProfile.enabled == True)
    )
    profile = r_res.scalar_one_or_none()
    if profile:
        ctx = profile.context_length
        if not ctx and profile.candidates:
            for c in profile.candidates:
                if c.is_active and c.model and c.model.context_length:
                    ctx = c.model.context_length
                    break
        ctx = ctx or 131072
        return {
            "license": "",
            "modelfile": f"# Modelfile for route/{profile.slug}\nFROM route/{profile.slug}\n",
            "parameters": "",
            "template": "{{ .Prompt }}",
            "system": "",
            "details": {
                "parent_model": "",
                "format": "api",
                "family": "router-profile",
                "families": ["router-profile"],
                "parameter_size": "unknown",
                "quantization_level": "none",
            },
            "model_info": {
                "general.architecture": "router",
                "context_length": ctx,
            },
        }

    # Check discovered models
    query = select(DiscoveredModel).where(
        DiscoveredModel.enabled == True,
        DiscoveredModel.available == True,
        DiscoveredModel.is_visible == True,
        DiscoveredModel.provider.has(Provider.enabled == True),
        (DiscoveredModel.canonical_slug == model_name) | (DiscoveredModel.provider_model_id == model_name),
    )
    result = await db.execute(query)
    model_obj = result.scalars().first()

    if not model_obj and ":" in model_name:
        # Strip tag e.g. "model:latest"
        base_name = model_name.split(":", 1)[0]
        query2 = select(DiscoveredModel).where(
            DiscoveredModel.enabled == True,
            DiscoveredModel.available == True,
            DiscoveredModel.is_visible == True,
            DiscoveredModel.provider.has(Provider.enabled == True),
            (DiscoveredModel.canonical_slug == base_name) | (DiscoveredModel.provider_model_id == base_name),
        )
        result2 = await db.execute(query2)
        model_obj = result2.scalars().first()

    if model_obj:
        ctx = model_obj.context_length or 131072
        max_out = model_obj.max_output_tokens or 4096
        return {
            "license": "",
            "modelfile": f"# Modelfile for {model_obj.canonical_slug}\nFROM {model_obj.canonical_slug}\n",
            "parameters": "",
            "template": "{{ .Prompt }}",
            "system": "",
            "details": {
                "parent_model": "",
                "format": "api",
                "family": _model_family(model_obj),
                "families": [_model_family(model_obj)],
                "parameter_size": "unknown",
                "quantization_level": "none",
            },
            "model_info": {
                "general.architecture": "custom",
                "context_length": ctx,
                "max_tokens": max_out,
            },
        }

    if model_name.startswith(("fusion/", "judge/")):
        kind = model_name.split("/", 1)[0]
        return {"license": "", "modelfile": f"FROM {model_name}\n", "parameters": "", "template": "{{ .Prompt }}", "system": "",
                "details": {"format": "api", "family": f"{kind}-profile", "families": [f"{kind}-profile"], "parameter_size": "unknown", "quantization_level": "none"},
                "model_info": {"general.architecture": kind, "context_length": card.context_length or 131072}}

    return JSONResponse(status_code=404, content={"error": f"model '{model_name}' not found"})

@router.get("/tags")
@router.post("/tags")
async def ollama_tags(db: AsyncSession = Depends(get_db), router_key: Optional[RouterApiKey] = Depends(get_router_key_dep)):
    cards = (await list_models(db, router_key)).data
    models = []
    for card in cards:
        kind = card.id.split("/", 1)[0]
        family = {"route": "router-profile", "fusion": "fusion-profile", "judge": "judge-profile"}.get(kind, kind)
        name = card.id if ":" in card.id else card.id + ":latest"
        models.append({"name": name, "model": name, "modified_at": datetime.now(timezone.utc).isoformat(), "size": 0,
            "digest": "sha256:" + "0" * 64,
            "details": {"parent_model": "", "format": "api", "family": family, "families": [family], "parameter_size": "unknown", "quantization_level": "none"}})
    return {"models": models}
