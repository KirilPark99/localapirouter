"""Profile context CRUD and public metadata, isolated SQLite, no providers called."""
import os
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.engine import make_url

from app.core.database import AsyncSessionLocal, engine
from app.api.deps import get_current_admin, get_router_key_dep
from app.api.admin import fusion, judges
from app.api.v1 import router as v1
from app.api import ollama
from app.models.entities import Provider, DiscoveredModel


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["fusion", "judge"])
async def test_profile_context_roundtrip_and_metadata(kind):
    path = Path(engine.url.database).resolve()
    assert path == Path(AsyncSessionLocal.kw["bind"].url.database).resolve()
    assert path == Path(make_url(os.environ["DATABASE_URL"]).database).resolve()
    assert path.name.startswith("myairouter_test_")
    suffix = uuid.uuid4().hex
    async with AsyncSessionLocal() as db:
        provider = Provider(name="synthetic", slug="context-" + suffix,
                            adapter_type="openai", base_url="https://fixture.invalid")
        db.add(provider)
        await db.flush()
        model = DiscoveredModel(provider_id=provider.id, provider_model_id="synthetic", display_name="synthetic",
                                canonical_slug=provider.slug + "/synthetic", context_length=8192)
        db.add(model)
        await db.commit()
        refs = {"provider_id": provider.id, "model_id": model.id}
    app = FastAPI()
    app.include_router(fusion.router, prefix="/api/admin")
    app.include_router(judges.router, prefix="/api/admin")
    app.include_router(v1.router)
    app.include_router(ollama.router, prefix="/api")
    app.dependency_overrides[get_current_admin] = lambda: "synthetic-admin"
    app.dependency_overrides[get_router_key_dep] = lambda: None
    payload: dict[str, Any] = dict(name="synthetic", slug="context-" + suffix, context_length=65536,
                   judge_provider_id=provider.id, judge_model_id=model.id)
    if kind == "fusion":
        payload.update(min_successful_candidates=1, participants=[refs])
    else:
        payload.update(candidates=[dict(refs, label="synthetic")], fallback_strongest_on_overflow=False)
    base = "/api/admin/" + ("fusion" if kind == "fusion" else "judges")
    alias = kind + "/" + payload["slug"]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
        created = await client.post(base, json=payload)
        assert created.status_code == 201, created.text
        target = base + "/" + str(created.json()["id"])
        assert created.json()["context_length"] == 65536
        for value in (200000, 128000, 0, None):
            saved = await client.put(target, json={"context_length": value})
            assert saved.status_code == 200, saved.text
            assert saved.json()["context_length"] == value
            # Each read uses a fresh database session, not the write's identity map.
            assert (await client.get(target)).json()["context_length"] == value
            assert next(p for p in (await client.get(base)).json() if p["id"] == created.json()["id"])["context_length"] == value
            omitted = await client.put(target, json={"name": "renamed"})
            assert omitted.json()["context_length"] == value
            assert (await client.get("/v1/models/" + alias)).json()["context_length"] == value
            assert next(p for p in (await client.get("/v1/models")).json()["data"] if p["id"] == alias)["context_length"] == value
            shown = await client.post("/api/show", json={"name": alias})
            assert shown.status_code == 200, shown.text
            assert shown.json()["model_info"]["context_length"] == (value or 131072)
        for invalid in (-1, 1.5, "NaN", "Infinity"):
            bad = await client.put(target, json={"context_length": invalid})
            assert bad.status_code == 422, bad.text
            assert (await client.get(target)).json()["context_length"] is None
        assert (await client.delete(target)).status_code == 200
        assert (await client.get(target)).status_code == 404
