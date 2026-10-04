"""Browser OAuth uses synthetic accounts and mocked token endpoints only."""
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from app.api.admin.modules import router
from app.api.deps import get_current_admin
from app.modules.base import ModuleManifest
from app.modules.loader import LoadedModule, ModuleLoader


@pytest.mark.asyncio
@pytest.mark.parametrize("module_id", ["agy_cli", "codex_cli", "grok_builder_cli"])
async def test_browser_oauth_start_and_cancel(monkeypatch, module_id):
    monkeypatch.setattr(ModuleLoader, "get_module", lambda mid: LoadedModule(
        manifest=ModuleManifest(id=mid, name=mid), status="ready"))
    app = FastAPI()
    app.include_router(router, prefix="/api/admin")
    app.dependency_overrides[get_current_admin] = lambda: "synthetic-admin"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        base = f"/api/admin/modules/{module_id}/oauth"
        response = await client.post(base + "/start", json={"proxy_id": None})
        assert response.status_code == 200, response.text
        started = response.json()
        params = parse_qs(urlsplit(started["auth_url"]).query)
        if module_id != "agy_cli":
            assert params["code_challenge_method"] == ["S256"]
            assert params["code_challenge"]
        else:
            assert params["access_type"] == ["offline"]
            assert params["prompt"] == ["consent"]
        assert params["state"]
        assert "access_token" not in json.dumps(started)
        session_url = base + "/" + started["session_id"]
        assert (await client.get(session_url)).json()["status"] == "pending"
        cancelled = await client.delete(session_url)
        assert cancelled.status_code == 200
        assert (await client.get(session_url)).status_code in (404, 410)


@pytest.mark.asyncio
@pytest.mark.parametrize("module_id", ["agy_cli", "codex_cli", "grok_builder_cli"])
async def test_browser_oauth_exchange_save_and_reauthorize(monkeypatch, module_id):
    import base64
    import hashlib
    import uuid
    from urllib.parse import urlencode
    from sqlalchemy import select
    from app.core.crypto import decrypt_secret
    from app.core.database import AsyncSessionLocal
    from app.models.entities import Provider, ProviderCredential, Proxy
    from app.services import module_oauth

    # Use ephemeral loopback ports and an isolated SQLite database; never real CLI files.
    config = {**module_oauth.CONFIG[module_id], "port": 0}
    monkeypatch.setitem(module_oauth.CONFIG, module_id, config)
    monkeypatch.setattr(ModuleLoader, "get_module", lambda mid: LoadedModule(
        manifest=ModuleManifest(id=mid, name=mid), status="ready"))
    async with AsyncSessionLocal() as db:
        provider = Provider(name=module_id, slug=f"module_{module_id}", adapter_type="custom_module", base_url="")
        other = Provider(name="other", slug="other-" + uuid.uuid4().hex, adapter_type="custom_module", base_url="")
        proxy = Proxy(name="synthetic-proxy", scheme="http", host="unit.invalid", port=3128, enabled=True)
        db.add_all([provider, other, proxy])
        await db.commit()
        wrong_profile = ProviderCredential(provider_id=other.id, name="other account", encrypted_api_key="dummy",
                                           key_fingerprint=uuid.uuid4().hex, masked_key="dummy")
        db.add(wrong_profile)
        await db.commit()
        proxy_id, wrong_id = proxy.id, wrong_profile.id

    calls = []
    auth_params = {}
    claim = {"email": "synthetic@example.invalid", "https://api.openai.com/auth": {"chatgpt_account_id": "synthetic-workspace"}}
    id_token = "dummy." + base64.urlsafe_b64encode(json.dumps(claim).encode()).decode().rstrip("=") + ".dummy"

    def upstream(request):
        assert str(request.url) == config["token"]
        body = parse_qs(request.content.decode())
        assert body["code"] == ["synthetic-code"]
        assert body["redirect_uri"] == auth_params["redirect_uri"]
        assert body["client_id"] == [config["client_id"]]
        if module_id == "agy_cli":
            assert body["client_secret"]  # Public native-app credential, not a user secret.
            assert "code_verifier" not in body
        else:
            verifier = body["code_verifier"][0]
            expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
            assert auth_params["code_challenge"] == [expected]
            assert len(verifier) == (128 if module_id == "grok_builder_cli" else 43)
        calls.append(request)
        return httpx.Response(200, json={"access_token": "synthetic-access-token", "refresh_token": "synthetic-refresh-token",
                                         "id_token": id_token, "expires_in": 3600})

    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as token_client:
        async def get_client(**kwargs):
            assert kwargs["proxy_url"] == "http://unit.invalid:3128"
            return token_client
        monkeypatch.setattr(module_oauth.http_client_manager, "get_client", get_client)
        app = FastAPI()
        app.include_router(router, prefix="/api/admin")
        app.dependency_overrides[get_current_admin] = lambda: "synthetic-admin"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            base = f"/api/admin/modules/{module_id}/oauth"
            assert (await client.post(base + "/start", json={"proxy_id": 999999})).status_code == 404
            profile_id = None
            for reauth in (False, True):
                started = (await client.post(base + "/start", json={"proxy_id": proxy_id})).json()
                auth_params = parse_qs(urlsplit(started["auth_url"]).query)
                session_url = base + "/" + started["session_id"]
                payload = {"name": "Synthetic browser profile", "proxy_id": proxy_id, "priority": 2, "weight": 3,
                           "notes": "synthetic notes", "fields": {"auth_json": "old-secret", "project_id": "synthetic-project"}}
                if reauth:
                    payload["profile_id"] = profile_id
                assert (await client.post(session_url + "/save", json=payload)).status_code == 409
                app.dependency_overrides[get_current_admin] = lambda: "other-admin"
                assert (await client.get(session_url)).status_code == 404
                app.dependency_overrides[get_current_admin] = lambda: "synthetic-admin"
                callback = auth_params["redirect_uri"][0] + "?" + urlencode({"code": "synthetic-code", "state": auth_params["state"][0]})
                for invalid in (callback.replace(auth_params["state"][0], "wrong"),
                                callback.replace(auth_params["state"][0], "%D0%B0"), callback.split("&state=")[0],
                                callback + "&state=duplicate", callback.replace("/callback?", "/wrong?")):
                    assert (await client.post(session_url + "/callback", json={"callback_url": invalid})).status_code == 400
                assert len(calls) == int(reauth)
                if reauth:
                    # Actual HTTP callback to the synthetic loopback listener; no provider network.
                    async with httpx.AsyncClient(trust_env=False) as loopback_client:
                        response = await loopback_client.get(callback)
                        assert response.status_code == 200
                        assert "synthetic-access-token" not in response.text
                else:
                    result = await client.post(session_url + "/callback", json={"callback_url": callback})
                    assert result.status_code == 200 and result.json()["status"] == "authorized"
                public = await client.get(session_url)
                assert public.json()["status"] == "authorized"
                assert public.headers["Cache-Control"] == "no-store"
                assert "synthetic-access-token" not in public.text
                assert (await client.post(session_url + "/callback", json={"callback_url": callback})).status_code == 409
                assert (await client.post(session_url + "/save", json={**payload, "proxy_id": None})).status_code == 409
                assert (await client.post(session_url + "/save", json={**payload, "profile_id": wrong_id})).status_code == 404
                saved = await client.post(session_url + "/save", json=payload)
                assert saved.status_code == 200, saved.text
                profile_id = saved.json()["id"]
                assert "synthetic-access-token" not in saved.text
                assert (await client.get(session_url)).status_code == 404
                profiles = await client.get(f"/api/admin/modules/{module_id}/profiles")
                assert "synthetic-access-token" not in profiles.text and "synthetic-refresh-token" not in profiles.text
                async with AsyncSessionLocal() as db:
                    cred = await db.get(ProviderCredential, profile_id)
                    fields = json.loads(decrypt_secret(cred.encrypted_api_key))
                    assert fields["access_token"] == "synthetic-access-token"
                    assert fields["auto_detect_local"] == "false" and fields["auth_json"] == ""
                    assert "synthetic-access-token" not in json.dumps(cred.metadata_json)
                    assert cred.proxy_id == proxy_id and cred.priority == 2 and cred.weight == 3
                    assert cred.notes == "synthetic notes"
                    if module_id == "codex_cli":
                        assert fields["account_id"] == "synthetic-workspace"
                    if module_id == "grok_builder_cli":
                        assert fields["email"] == "synthetic@example.invalid"
                    assert len((await db.execute(select(ProviderCredential).where(ProviderCredential.provider_id == provider.id))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_oauth_expiry_errors_busy_port_and_auth_gate(monkeypatch):
    import socket
    from urllib.parse import urlencode
    from app.services import module_oauth

    app = FastAPI()
    app.include_router(router, prefix="/api/admin")
    monkeypatch.setattr(ModuleLoader, "get_module", lambda mid: LoadedModule(
        manifest=ModuleManifest(id=mid, name=mid), status="ready"))
    base = "/api/admin/modules/codex_cli/oauth"
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        config = {**module_oauth.CONFIG["codex_cli"], "port": occupied.getsockname()[1]}
        monkeypatch.setitem(module_oauth.CONFIG, "codex_cli", config)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.post(base + "/start", json={})).status_code == 401
            app.dependency_overrides[get_current_admin] = lambda: "synthetic-admin"
            started = (await client.post(base + "/start", json={})).json()
            assert started["loopback"] is False
            params = parse_qs(urlsplit(started["auth_url"]).query)
            assert urlsplit(params["redirect_uri"][0]).port == config["port"]
            session_url = base + "/" + started["session_id"]
            assert (await client.get(session_url.replace("codex_cli", "agy_cli"))).status_code == 404
            session = module_oauth.sessions[started["session_id"]]
            session.expires_at = 0
            assert (await client.get(session_url)).status_code == 410
            assert started["session_id"] not in module_oauth.sessions

            for status in (401, 200):
                async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(
                    status, json={"error": "sensitive-code-and-token"}))) as token_client:
                    async def fake_client(**kwargs):
                        return token_client
                    monkeypatch.setattr(module_oauth.http_client_manager, "get_client", fake_client)
                    started = (await client.post(base + "/start", json={})).json()
                    params = parse_qs(urlsplit(started["auth_url"]).query)
                    callback = params["redirect_uri"][0] + "?" + urlencode({"code": "fake", "state": params["state"][0]})
                    session_url = base + "/" + started["session_id"]
                    result = await client.post(session_url + "/callback", json={"callback_url": callback})
                    assert result.status_code == 200 and result.json()["status"] == "error"
                    assert "sensitive-code-and-token" not in result.text
                    assert (await client.post(session_url + "/save", json={"name": "fake"})).status_code == 409
                    assert (await client.delete(session_url)).status_code == 200
            # Explicit user denial is terminal and never invokes a token endpoint.
            async def forbidden(**kwargs):
                raise AssertionError("User denial must not exchange tokens")
            monkeypatch.setattr(module_oauth.http_client_manager, "get_client", forbidden)
            started = (await client.post(base + "/start", json={})).json()
            params = parse_qs(urlsplit(started["auth_url"]).query)
            callback = params["redirect_uri"][0] + "?" + urlencode({"error": "access_denied", "state": params["state"][0]})
            session_url = base + "/" + started["session_id"]
            result = await client.post(session_url + "/callback", json={"callback_url": callback})
            assert result.json()["status"] == "error"
            await client.delete(session_url)


@pytest.mark.asyncio
async def test_parallel_oauth_start_replaces_previous(monkeypatch):
    import asyncio
    from app.services import module_oauth

    monkeypatch.setitem(module_oauth.CONFIG, "agy_cli", {**module_oauth.CONFIG["agy_cli"], "port": 0})
    start_server = asyncio.start_server

    async def delayed_listener(*args, **kwargs):
        await asyncio.sleep(0.01)  # Force overlapping starts without provider network.
        return await start_server(*args, **kwargs)

    monkeypatch.setattr(asyncio, "start_server", delayed_listener)
    try:
        results = await asyncio.gather(*(module_oauth.start("agy_cli", "synthetic-admin", None, None) for _ in range(3)))
        alive = [r["session_id"] for r in results if r["session_id"] in module_oauth.sessions]
        assert alive == [results[-1]["session_id"]]
        await module_oauth.close_all()
        for index in range(31):
            module_oauth.sessions[f"synthetic-limit-{index}"] = module_oauth.OAuthSession(
                "agy_cli", f"existing-{index}", None, None)
        limited = await asyncio.gather(*(module_oauth.start("agy_cli", f"new-{i}", None, None)
                                         for i in range(3)), return_exceptions=True)
        assert len(module_oauth.sessions) == 32
        assert sum(isinstance(result, dict) for result in limited) == 1
        rejected = [result for result in limited if isinstance(result, Exception)]
        assert len(rejected) == 2
        assert all(isinstance(result, HTTPException) and result.status_code == 429 for result in rejected)
    finally:
        await module_oauth.close_all()


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["expire_while_waiting", "cancel_during_save"])
async def test_oauth_save_lifecycle_races(monkeypatch, scenario):
    import asyncio
    import importlib
    from app.services import module_oauth

    api = importlib.import_module("app.api.admin.modules")
    app = FastAPI()
    app.include_router(router, prefix="/api/admin")
    app.dependency_overrides[get_current_admin] = lambda: "synthetic-admin"
    session = module_oauth.OAuthSession("agy_cli", "synthetic-admin", None, None,
                                       status="authorized", tokens={"access_token": "synthetic-token"})
    sid = "synthetic-race"
    module_oauth.sessions[sid] = session
    entered, release = asyncio.Event(), asyncio.Event()
    writes = []

    async def fake_save(module_id, data, db):
        entered.set()
        await release.wait()
        writes.append(dict(data.fields))
        return {"id": 123}

    monkeypatch.setattr(api, "create_module_profile", fake_save)
    base = f"/api/admin/modules/agy_cli/oauth/{sid}"
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            if scenario == "expire_while_waiting":
                await session.lock.acquire()
                retrieved = asyncio.Event()
                get_session = module_oauth.get_session

                def observed_session(*args):
                    result = get_session(*args)
                    retrieved.set()
                    return result

                monkeypatch.setattr(module_oauth, "get_session", observed_session)
                task = asyncio.create_task(client.post(base + "/save", json={"name": "Synthetic"}))
                await asyncio.wait_for(retrieved.wait(), 1)
                session.expires_at = 0
                release.set()
                session.lock.release()
                response = await asyncio.wait_for(task, 1)
                assert response.status_code == 410
                assert not writes
            else:
                task = asyncio.create_task(client.post(base + "/save", json={"name": "Synthetic"}))
                await asyncio.wait_for(entered.wait(), 1)
                cancel = asyncio.create_task(client.delete(base))
                await asyncio.sleep(0.02)
                was_waiting = not cancel.done()
                release.set()
                saved, cancelled = await asyncio.wait_for(asyncio.gather(task, cancel), 1)
                assert was_waiting, "Cancellation must not report success while persistence is still in flight"
                assert saved.status_code == 200 and cancelled.status_code == 200
                assert len(writes) == 1
                assert (await client.post(base + "/save", json={"name": "Again"})).status_code == 404
    finally:
        release.set()
        if session.lock.locked():
            session.lock.release()
        await module_oauth.close_all()


