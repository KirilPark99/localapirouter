"""Offline signed-token OIDC regressions; uses conftest's unique synthetic DB."""
import asyncio
import json
import time
import uuid
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi import FastAPI
from sqlalchemy import func, select


from app.api.admin.auth import router
from app.core import database
from app.core.config import settings
from app.models.entities import AdminUser
from app.security.registry import GuardrailRegistry
from app.services.auth_service import AuthService
from app.services.oidc_service import OidcService


@pytest.fixture(scope="module")
def signing_keys():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048), ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def provider(monkeypatch, signing_keys):
    OidcService._transactions.clear()
    cfg = {"oidc_enabled": True, "oidc_issuer": "https://provider.invalid", "oidc_client_id": "fixture-client",
           "oidc_client_secret": "synthetic-secret", "oidc_allowed_emails": ["approved@example.invalid"]}
    async def config(cls, db):
        return cfg
    monkeypatch.setattr(GuardrailRegistry, "get_security_config", classmethod(config))
    p = {"cfg": cfg, "nonce": "", "sub": uuid.uuid4().hex, "changes": {}, "ui_changes": {}, "algorithm": "RS256",
         "calls": [], "key": signing_keys[0], "signing_keys": signing_keys, "token_mode": "valid", "ui_status": 200}
    async def upstream(request):
        p["calls"].append(request.url.path)
        assert request.url.host == "provider.invalid", "Unexpected provider network target"
        if request.url.path.endswith("openid-configuration"):
            issuer = cfg["oidc_issuer"]
            return httpx.Response(200, json={"issuer": p.get("discovery_issuer", issuer),
                "authorization_endpoint": issuer + "/authorize", "token_endpoint": issuer + "/token",
                "userinfo_endpoint": issuer + "/userinfo", "jwks_uri": issuer + "/jwks",
                "id_token_signing_alg_values_supported": ["RS256", "ES256", "PS256"]})
        if request.url.path == "/token":
            body = parse_qs(request.content.decode())
            assert body["redirect_uri"] == ["http://test/auth/oidc/callback"]
            claims = {"iss": cfg["oidc_issuer"], "sub": p["sub"], "aud": cfg["oidc_client_id"],
                      "iat": int(time.time()), "exp": int(time.time()) + 300, "nonce": p["nonce"]}
            claims.update(p["changes"])
            for name in p.get("remove", []):
                claims.pop(name, None)
            mode = p["token_mode"]
            key = p["key"] if mode != "wrong-signature" else rsa.generate_private_key(public_exponent=65537, key_size=2048)
            algorithm = p["algorithm"]
            if mode == "none":
                token = jwt.encode(claims, None, algorithm="none")
            elif mode == "hs":
                token = jwt.encode(claims, "synthetic-attacker-secret-long-enough-for-HS256", algorithm="HS256")
            else:
                token = jwt.encode(claims, key, algorithm=algorithm, headers={"kid": "fixture-key"})
            payload = {"access_token": "synthetic-provider-access", "id_token": token}
            if mode == "missing":
                del payload["id_token"]
            if mode == "garbage":
                payload["id_token"] = "not.a.jwt"
            return httpx.Response(200, json=payload)
        if request.url.path == "/jwks":
            algorithm = p["algorithm"]
            cls = jwt.algorithms.ECAlgorithm if algorithm.startswith("ES") else jwt.algorithms.RSAAlgorithm
            jwk = json.loads(cls.to_jwk(p["key"].public_key()))
            jwk.update({"kid": "fixture-key", "use": "sig", "alg": algorithm})
            jwk.update(p.get("jwk_changes", {}))
            return httpx.Response(200, json={"keys": [jwk]})
        if request.url.path == "/userinfo":
            assert request.headers["authorization"] == "Bearer synthetic-provider-access"
            ui = {"sub": p["sub"], "email": "approved@example.invalid", "email_verified": True}
            ui.update(p["ui_changes"])
            return httpx.Response(p["ui_status"], json=ui)
        raise AssertionError(request.url)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: real_client(*args, **kwargs, transport=httpx.MockTransport(upstream)))
    app = FastAPI()
    app.include_router(router)
    p["client"] = lambda: real_client(transport=httpx.ASGITransport(app=app), base_url="http://test", follow_redirects=False)
    yield p
    OidcService._transactions.clear()


async def begin(p, client, json_mode=True):
    response = await client.get("/auth/oidc/login", headers={"accept": "application/json" if json_mode else "text/html"})
    assert response.status_code == (200 if json_mode else 302)
    url = response.json()["authorization_url"] if json_mode else response.headers["location"]
    params = parse_qs(urlsplit(url).query)
    assert params["scope"][0].split().count("openid") == 1
    p["nonce"] = params["nonce"][0]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert ("Secure" in response.headers["set-cookie"]) == settings.COOKIE_SECURE
    return params["state"][0]


async def admin_count():
    async with database.AsyncSessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(AdminUser))


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["missing", "mismatch", "nonascii", "empty", "duplicate", "wrong-browser", "no-cookie", "expired", "redirect-mismatch"])
async def test_p08_invalid_state_rejected_before_exchange(provider, case):
    p = provider
    before = await admin_count()
    async with p["client"]() as browser:
        state = await begin(p, browser)
        params = {"code": "synthetic-code", "state": state}
        if case == "missing":
            del params["state"]
        elif case == "mismatch":
            params["state"] = "wrong-state"
        elif case == "nonascii":
            params["state"] = "чужой-state"
        elif case == "empty":
            params["state"] = ""
        elif case == "duplicate":
            params = [("code", "synthetic-code"), ("state", state), ("state", state)]
        elif case == "wrong-browser":
            browser.cookies.set("oidc_browser", "wrong-browser")
        elif case == "no-cookie":
            browser.cookies.clear()
        elif case == "expired":
            OidcService._transactions[state]["expires"] = time.monotonic() - 1
        elif case == "redirect-mismatch":
            OidcService._transactions[state]["redirect_uri"] = "http://other/callback"
        response = await browser.get("/auth/oidc/callback", params=params)
        assert response.status_code == 400
        assert "/token" not in p["calls"]
        assert "access_token" not in browser.cookies
    assert await admin_count() == before


@pytest.mark.asyncio
async def test_p08_browser_binding_replay_and_concurrent_callback(provider):
    p = provider
    async with p["client"]() as browser, p["client"]() as stranger:
        state = await begin(p, browser)
        params = {"code": "synthetic-code", "state": state}
        assert (await stranger.get("/auth/oidc/callback", params=params)).status_code == 400
        responses = await asyncio.gather(*(browser.get("/auth/oidc/callback", params=params) for _ in range(2)))
        assert sorted(r.status_code for r in responses) == [302, 400]
        assert p["calls"].count("/token") == 1
        browser.cookies.set("oidc_browser", "restored-cookie")
        assert (await browser.get("/auth/oidc/callback", params=params)).status_code == 400
        assert p["calls"].count("/token") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["iss", "aud", "exp", "nonce", "nonce-nonascii", "azp", "multi-aud", "missing-exp", "missing-iat", "missing-sub", "missing-nonce", "empty-sub", "wrong-signature", "none", "hs", "missing", "garbage", "userinfo-sub", "userinfo-error", "unverified", "string-verified", "email", "sub-as-email", "jwk-use", "jwk-alg", "discovery-issuer"])
async def test_p09_invalid_identity_never_provisions(provider, case):
    p = provider
    before = await admin_count()
    async with p["client"]() as browser:
        state = await begin(p, browser)
        if case in ("iss", "aud", "nonce", "azp"):
            p["changes"][case] = "wrong"
        elif case == "exp":
            p["changes"]["exp"] = int(time.time()) - 10
        elif case == "nonce-nonascii":
            p["changes"]["nonce"] = "неnonce"
        elif case == "multi-aud":
            p["changes"]["aud"] = [p["cfg"]["oidc_client_id"], "other-client"]
        elif case.startswith("missing-"):
            p["remove"] = [case.removeprefix("missing-")]
        elif case == "empty-sub":
            p["changes"]["sub"] = ""
        elif case in ("wrong-signature", "none", "hs", "missing", "garbage"):
            p["token_mode"] = case
        elif case == "userinfo-sub":
            p["ui_changes"]["sub"] = "other-user"
        elif case == "userinfo-error":
            p["ui_status"] = 503
        elif case in ("unverified", "string-verified"):
            p["ui_changes"]["email_verified"] = False if case == "unverified" else "true"
        elif case == "email":
            p["ui_changes"]["email"] = "not-allowed@example.invalid"
        elif case == "sub-as-email":
            p["cfg"]["oidc_allowed_emails"] = [p["sub"]]
        elif case.startswith("jwk-"):
            p["jwk_changes"] = {case.removeprefix("jwk-"): "enc" if case == "jwk-use" else "HS256"}
        elif case == "discovery-issuer":
            p["discovery_issuer"] = "https://other.invalid"
        response = await browser.get("/auth/oidc/callback", params={"code": "synthetic-code", "state": state})
        assert response.status_code == (403 if case in ("unverified", "string-verified", "email", "sub-as-email") else 400)
        assert "access_token" not in browser.cookies
    assert await admin_count() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("algorithm", ["RS256", "ES256", "PS256"])
async def test_p09_p51_signed_sso_has_stable_active_local_principal_and_me(provider, algorithm):
    p = provider
    p["algorithm"] = algorithm
    p["key"] = p["signing_keys"][1 if algorithm.startswith("ES") else 0]
    p["changes"].update({"aud": [p["cfg"]["oidc_client_id"], "other"], "azp": p["cfg"]["oidc_client_id"]})
    username = OidcService.principal_username(p["cfg"]["oidc_issuer"], p["sub"])
    before = await admin_count()
    async with p["client"]() as browser:
        for json_mode in (True, False):
            state = await begin(p, browser, json_mode)
            result = await browser.get("/auth/oidc/callback", params={"code": "synthetic-code", "state": state})
            assert result.status_code == 302
            assert result.headers["location"] == "/"
            assert "oidc_browser" not in browser.cookies
            assert AuthService.verify_access_token(browser.cookies["access_token"]) == username
            me = await browser.get("/auth/me")
            assert me.status_code == 200
            assert me.json() == {"username": username, "authenticated": True}
            async with database.AsyncSessionLocal() as db:
                row = (await db.execute(select(AdminUser).where(AdminUser.username == username))).scalar_one()
                assert row.is_active and row.password_hash.startswith("$2")
        assert await admin_count() == before + 1
        async with database.AsyncSessionLocal() as db:
            row = (await db.execute(select(AdminUser).where(AdminUser.username == username))).scalar_one()
            row.is_active = False
            old_hash = row.password_hash
            await db.commit()
        assert (await browser.get("/auth/me")).status_code == 401
        browser.cookies.clear()
        state = await begin(p, browser)
        assert (await browser.get("/auth/oidc/callback", params={"code": "synthetic-code", "state": state})).status_code == 403
        assert "access_token" not in browser.cookies
        async with database.AsyncSessionLocal() as db:
            row = (await db.execute(select(AdminUser).where(AdminUser.username == username))).scalar_one()
            assert not row.is_active and row.password_hash == old_hash


@pytest.mark.asyncio
async def test_p51_empty_whitelist_allows_provider_user_not_local_password_username(provider):
    p = provider
    p["cfg"]["oidc_allowed_emails"] = []
    p["sub"] = settings.ADMIN_USERNAME
    p["ui_changes"] = {"email": settings.ADMIN_USERNAME, "email_verified": False}
    username = OidcService.principal_username(p["cfg"]["oidc_issuer"], p["sub"])
    async with database.AsyncSessionLocal() as db:
        local = (await db.execute(select(AdminUser).where(AdminUser.username == settings.ADMIN_USERNAME))).scalar_one()
        local_hash = local.password_hash
    async with p["client"]() as browser:
        state = await begin(p, browser)
        assert (await browser.get("/auth/oidc/callback", params={"code": "synthetic-code", "state": state})).status_code == 302
        assert (await browser.get("/auth/me")).json()["username"] == username != settings.ADMIN_USERNAME
    async with database.AsyncSessionLocal() as db:
        local = (await db.execute(select(AdminUser).where(AdminUser.username == settings.ADMIN_USERNAME))).scalar_one()
        assert local.password_hash == local_hash
    assert username != OidcService.principal_username("https://other.invalid", p["sub"])


@pytest.mark.asyncio
@pytest.mark.parametrize("winner_active", [True, False])
async def test_p51_provision_unique_constraint_race_rolls_back_and_respects_winner(provider, monkeypatch, winner_active):
    p = provider
    username = OidcService.principal_username(p["cfg"]["oidc_issuer"], p["sub"])
    original_commit = database.AsyncSession.commit
    raced = False
    async def racing_commit(db):
        nonlocal raced
        if not raced and any(isinstance(row, AdminUser) and row.username == username for row in db.new):
            raced = True
            async with database.AsyncSessionLocal() as other:
                other.add(AdminUser(username=username, password_hash=AuthService.hash_password("fixture-race-password"), is_active=winner_active))
                await original_commit(other)
            # The real commit below hits SQLite's unique constraint against the winner.
        return await original_commit(db)
    monkeypatch.setattr(database.AsyncSession, "commit", racing_commit)
    async with p["client"]() as browser:
        state = await begin(p, browser)
        response = await browser.get("/auth/oidc/callback", params={"code": "synthetic-code", "state": state})
        assert response.status_code == (302 if winner_active else 403)
        assert raced
        assert (await browser.get("/auth/me")).status_code == (200 if winner_active else 401)
    async with database.AsyncSessionLocal() as db:
        rows = (await db.execute(select(AdminUser).where(AdminUser.username == username))).scalars().all()
        assert len(rows) == 1 and rows[0].is_active == winner_active
