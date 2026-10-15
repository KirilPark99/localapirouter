"""Offline ASGI login contract; synthetic DB/adapter only, no bridge or credential files."""
import uuid
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.admin import modules
from app.api.deps import get_current_admin
from app.core.crypto import encrypt_secret
from app.core.database import Base, get_db
from app.models.entities import Provider, ProviderCredential
from app.modules.loader import ModuleLoader


@pytest.mark.asyncio
async def test_profile_scoped_login_contract(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessions() as db:
        providers = [Provider(id=i, name=slug, slug=slug, adapter_type="custom_module", base_url="",
                              configuration={"module_id": slug.removeprefix("module_")})
                     for i, slug in enumerate(("module_freebuff", "module_other"), 1)]
        db.add_all(providers)
        db.add_all([ProviderCredential(id=i, provider_id=1 if i < 3 else 2, name=str(i),
                    encrypted_api_key=encrypt_secret('{"admin_token":"synthetic-secret","base_url":"http://bridge.invalid"}'),
                    key_fingerprint=str(i), masked_key="masked", metadata_json={}) for i in range(1, 4)])
        await db.commit()

    calls, state = [], {"status": "pending", "url": "https://freebuff.com/cli?code=synthetic"}
    flow_id = str(uuid.uuid4())

    async def start(ctx):
        assert ctx.credentials["admin_token"] == "synthetic-secret"
        assert ctx.extra_config["credential_id"] == 1
        calls.append("start")
        return {"flow": {"id": flow_id, "loginUrl": state["url"], "status": state["status"],
                "expiresAt": None, "createdAt": None, "authToken": "do-not-expose",
                "user": {"authToken": "do-not-expose"}}, "token": "do-not-expose"}

    async def status(ctx, fid):
        assert ctx.extra_config["credential_id"] == 1 and fid == flow_id
        calls.append("status")
        if state.get("fail"):
            raise ValueError("synthetic-secret http://sensitive-proxy")
        return {"flow": {"id": state.get("id", fid), "loginUrl": state["url"], "status": state["status"],
                         "error": state.get("error"), "authToken": "do-not-expose"}}

    async def cancel(ctx, fid):
        assert ctx.extra_config["credential_id"] == 1 and fid == flow_id
        calls.append("cancel")
        return {"flow": {"id": fid, "loginUrl": state["url"], "status": "cancelled", "secret": "do-not-expose"}}

    adapter = SimpleNamespace(login_start=start, login_status=status, login_cancel=cancel)
    monkeypatch.setattr(ModuleLoader, "get_adapter", lambda mid: adapter if mid == "freebuff" else None)
    modules._freebuff_login_flows.clear()
    app = FastAPI()
    app.include_router(modules.router, prefix="/api/admin")

    async def db_dependency():
        async with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = db_dependency
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            base = "/api/admin/modules/freebuff/profiles/1/login"
            assert (await client.post(base)).status_code == 401
            assert (await client.get(base + "/" + flow_id)).status_code == 401
            assert (await client.post(base + "/" + flow_id + "/cancel")).status_code == 401
            app.dependency_overrides[get_current_admin] = lambda: "synthetic-admin"
            for profile in (3, 999):
                assert (await client.post(base.replace("/1/", f"/{profile}/"))).status_code == 404
            response = await client.post(base)
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "no-store"
            assert set(response.json()) == {"flow"}
            assert set(response.json()["flow"]) == {"id", "loginUrl", "status", "expiresAt", "createdAt"}
            assert "do-not-expose" not in response.text
            url = base + "/" + flow_id
            before = list(calls)
            assert (await client.get(base + "/not-a-uuid")).status_code == 422
            assert (await client.post(base + "/not-a-uuid/cancel")).status_code == 422
            assert (await client.get(url.replace("/1/", "/2/"))).status_code == 404
            assert (await client.post(url.replace("/1/", "/2/") + "/cancel")).status_code == 404
            app.dependency_overrides[get_current_admin] = lambda: "other-admin"
            assert (await client.get(url)).status_code == 404
            assert (await client.post(url + "/cancel")).status_code == 404
            assert calls == before
            app.dependency_overrides[get_current_admin] = lambda: "synthetic-admin"
            assert (await client.get(url)).json()["flow"]["status"] == "pending"
            state["error"] = "synthetic-secret http://sensitive-proxy"
            response = await client.get(url)
            assert response.json()["flow"]["error"] and "synthetic-secret" not in response.text
            state.pop("error")
            state["id"] = str(uuid.uuid4())
            assert (await client.get(url)).status_code == 502
            state.pop("id")
            state["status"] = "done"
            assert (await client.get(url)).json()["flow"]["status"] == "done"
            state["fail"] = True
            response = await client.get(url)
            assert response.status_code == 502 and "synthetic-secret" not in response.text
            state["fail"] = False
            response = await client.post(url + "/cancel")
            assert response.json()["flow"]["status"] == "cancelled" and response.headers["cache-control"] == "no-store"
            assert "do-not-expose" not in response.text
            assert (await client.get(url)).status_code == 404
            assert (await client.post(base)).status_code == 200
            owned = modules._freebuff_login_flows[flow_id]
            modules._freebuff_login_flows[flow_id] = (*owned[:3], 0)
            before = list(calls)
            assert (await client.get(url)).status_code == 404 and calls == before
            assert flow_id not in modules._freebuff_login_flows
            for unsafe in ("javascript:alert(1)", "https://evil.invalid", "https://user:pass@freebuff.com", "https://freebuff.com:444"):
                state["url"] = unsafe
                assert (await client.post(base)).status_code == 502
            state["url"] = "https://freebuff.com/cli?code=synthetic"
            assert (await client.post(base)).status_code == 200
            state["url"] = "https://www.codebuff.com/cli?code=synthetic"
            assert (await client.post(base)).status_code == 200
            async with sessions() as db:
                cred = await db.get(ProviderCredential, 1)
                cred.created_at += timedelta(seconds=1)
                await db.commit()
            before = list(calls)
            assert (await client.get(url)).status_code == 404
            assert (await client.post(url + "/cancel")).status_code == 404
            assert calls == before, "reused numeric credential ID must not inherit a flow"
            async with sessions() as db:
                provider = await db.get(Provider, 1)
                provider.configuration = {"module_id": "other"}
                await db.commit()
            assert (await client.post(base)).status_code == 404 and calls == before
            async with sessions() as db:
                provider = await db.get(Provider, 1)
                provider.configuration = {"module_id": "freebuff"}
                await db.commit()
            monkeypatch.setattr(ModuleLoader, "get_adapter", lambda mid: SimpleNamespace())
            assert (await client.post(base)).status_code == 503
    finally:
        modules._freebuff_login_flows.clear()
        await engine.dispose()
