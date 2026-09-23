import pytest
import uuid
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.entities import Provider, DiscoveredModel, RoutingProfile, FusionProfile


@pytest.mark.asyncio
async def test_ollama_version_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/version")
        assert res.status_code == 200
        data = res.json()
        assert "version" in data
        assert data["version"] == "0.5.4"


@pytest.mark.asyncio
async def test_ollama_tags_and_show():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p = Provider(
            name=f"Ollama Prov {run_id}", slug=f"ollama-p-{run_id}", adapter_type="openai",
            base_url="https://api.openai.com/v1", models_endpoint="/models",
            chat_endpoint="/chat/completions", enabled=True,
            auth_type="bearer", auth_header="Authorization",
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)

        model = DiscoveredModel(
            provider_id=p.id,
            provider_model_id=f"gpt-4o-{run_id}",
            canonical_slug=f"openai/gpt-4o-{run_id}",
            display_name=f"GPT-4o {run_id}",
            context_length=128000,
            max_output_tokens=4096,
            enabled=True,
            available=True,
            is_visible=True,
        )
        db.add(model)

        route = RoutingProfile(
            name=f"Route {run_id}",
            slug=f"route-{run_id}",
            strategy="fallback",
            enabled=True,
            context_length=64000,
        )
        db.add(route)

        await db.commit()
        await db.refresh(model)

        fusion = FusionProfile(
            name=f"Fusion {run_id}",
            slug=f"fusion-{run_id}",
            strategy="synthesize",
            judge_provider_id=p.id,
            judge_model_id=model.id,
            enabled=True,
        )
        db.add(fusion)
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test GET /api/tags
        res = await client.get("/api/tags")
        assert res.status_code == 200
        tags_data = res.json()
        assert "models" in tags_data
        model_names = [m["name"] for m in tags_data["models"]]
        assert f"openai/gpt-4o-{run_id}:latest" in model_names
        assert f"route/route-{run_id}:latest" in model_names

        # 2. Test POST /api/tags (Ollama clients sometimes use POST)
        res_post = await client.post("/api/tags")
        assert res_post.status_code == 200
        assert "models" in res_post.json()

        # 3. Test POST /api/show for discovered model
        res_show_model = await client.post(
            "/api/show",
            json={"name": f"openai/gpt-4o-{run_id}"}
        )
        assert res_show_model.status_code == 200
        show_m = res_show_model.json()
        assert f"Modelfile for openai/gpt-4o-{run_id}" in show_m["modelfile"]
        assert show_m["model_info"]["context_length"] == 128000
        assert show_m["details"]["family"] == "openai"

        # 4. Test POST /api/show with tag ":latest"
        res_show_tag = await client.post(
            "/api/show",
            json={"model": f"openai/gpt-4o-{run_id}:latest"}
        )
        assert res_show_tag.status_code == 200
        assert show_m["model_info"]["context_length"] == 128000

        # 5. Test POST /api/show for route profile
        res_show_route = await client.post(
            "/api/show",
            json={"name": f"route/route-{run_id}"}
        )
        assert res_show_route.status_code == 200
        show_r = res_show_route.json()
        assert show_r["details"]["family"] == "router-profile"
        assert show_r["model_info"]["general.architecture"] == "router"

        # 6. Test POST /api/show for fusion profile
        res_show_fusion = await client.post(
            "/api/show",
            json={"name": f"fusion/fusion-{run_id}"}
        )
        assert res_show_fusion.status_code == 200
        show_f = res_show_fusion.json()
        assert show_f["details"]["family"] == "fusion-profile"
        assert show_f["model_info"]["general.architecture"] == "fusion"

        # 7. Test POST /api/show with empty body
        res_empty = await client.post("/api/show", json={})
        assert res_empty.status_code == 400

        # 8. Test POST /api/show for unknown model
        res_404 = await client.post("/api/show", json={"name": "non-existent-model-xyz"})
        assert res_404.status_code == 404
