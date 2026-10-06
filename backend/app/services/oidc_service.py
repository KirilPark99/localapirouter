"""OIDC authorization-code login with browser-bound, one-use transactions."""
import hashlib
import json
import secrets
import time
import urllib.parse
from typing import Any, Dict, Optional

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AdminUser
from app.security.registry import GuardrailRegistry
from app.services.auth_service import AuthService


class OidcService:
    STATE_TTL = 300
    STATE_LIMIT = 1024
    # ponytail: process-local transactions; shared TTL store if multiple workers are deployed.
    _transactions: Dict[str, Dict[str, Any]] = {}
    PUBLIC_ALGORITHMS = {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512"}

    @classmethod
    async def get_oidc_endpoints(cls, issuer: str) -> Dict[str, Any]:
        issuer_url = urllib.parse.urlsplit(issuer)
        if issuer_url.scheme != "https" or not issuer_url.netloc or issuer_url.query or issuer_url.fragment or issuer_url.username:
            raise ValueError("Invalid OIDC issuer")
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{issuer.rstrip('/')}/.well-known/openid-configuration")
            resp.raise_for_status()
            data = resp.json()
        if data.get("issuer") != issuer:
            raise ValueError("OIDC discovery issuer mismatch")
        for name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            url = urllib.parse.urlsplit(data.get(name, ""))
            if url.scheme != "https" or not url.netloc or url.fragment or url.username:
                raise ValueError("Invalid OIDC discovery endpoint")
        if data.get("userinfo_endpoint"):
            url = urllib.parse.urlsplit(data["userinfo_endpoint"])
            if url.scheme != "https" or not url.netloc or url.fragment or url.username:
                raise ValueError("Invalid OIDC userinfo endpoint")
        return data

    @classmethod
    async def get_authorization_url(
        cls, db: AsyncSession, redirect_uri: str, *, browser_binding: str
    ) -> Optional[str]:
        cfg = await GuardrailRegistry.get_security_config(db)
        if not cfg.get("oidc_enabled"):
            return None
        issuer = cfg.get("oidc_issuer", "").strip()
        client_id = cfg.get("oidc_client_id", "").strip()
        if not issuer or not client_id:
            return None
        endpoints = await cls.get_oidc_endpoints(issuer)
        now = time.monotonic()
        for key, entry in list(cls._transactions.items()):
            if entry["expires"] <= now:
                del cls._transactions[key]
        if len(cls._transactions) >= cls.STATE_LIMIT:
            raise ValueError("Too many pending OIDC logins")
        state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        cls._transactions[state] = {
            "binding": browser_binding, "nonce": nonce, "redirect_uri": redirect_uri,
            "issuer": issuer, "client_id": client_id, "expires": now + cls.STATE_TTL,
        }
        scopes = cfg.get("oidc_scopes") or ["openid", "profile", "email"]
        params = {
            "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
            "scope": " ".join(dict.fromkeys(["openid", *scopes])),
            "state": state, "nonce": nonce, "prompt": "select_account",
        }
        separator = "&" if "?" in endpoints["authorization_endpoint"] else "?"
        return endpoints["authorization_endpoint"] + separator + urllib.parse.urlencode(params)

    @classmethod
    def consume_state(cls, state: Optional[str], browser_binding: Optional[str], redirect_uri: str) -> Dict[str, Any]:
        if not state or not browser_binding or not state.isascii() or not browser_binding.isascii():
            raise ValueError("Missing or invalid OIDC state")
        if len(state) > 128 or len(browser_binding) > 128:
            raise ValueError("Invalid OIDC state")
        entry = cls._transactions.get(state)
        if not entry or entry["expires"] <= time.monotonic():
            cls._transactions.pop(state, None)
            raise ValueError("Expired or already used OIDC state")
        if not secrets.compare_digest(entry["binding"], browser_binding) or entry["redirect_uri"] != redirect_uri:
            raise ValueError("OIDC state does not match this browser")
        # No await between checking and popping: only one callback can exchange.
        return cls._transactions.pop(state)

    @staticmethod
    def principal_username(issuer: str, sub: str) -> str:
        identity = json.dumps([issuer, sub], ensure_ascii=True, separators=(",", ":"))
        return "oidc:" + hashlib.sha256(identity.encode()).hexdigest()

    @classmethod
    async def exchange_code(cls, db: AsyncSession, code: str, redirect_uri: str, *, transaction: Dict[str, Any]) -> Dict[str, Any]:
        cfg = await GuardrailRegistry.get_security_config(db)
        issuer = cfg.get("oidc_issuer", "").strip()
        client_id = cfg.get("oidc_client_id", "").strip()
        if not cfg.get("oidc_enabled") or not issuer or not client_id:
            raise ValueError("OIDC authentication is not configured")
        if (issuer, client_id, redirect_uri) != (transaction["issuer"], transaction["client_id"], transaction["redirect_uri"]):
            raise ValueError("OIDC configuration changed during login")
        if transaction["expires"] <= time.monotonic():
            raise ValueError("OIDC login expired")
        endpoints = await cls.get_oidc_endpoints(issuer)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(endpoints["token_endpoint"], data={
                "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
                "client_id": client_id, "client_secret": cfg.get("oidc_client_secret", "").strip(),
            })
            resp.raise_for_status()
            tokens = resp.json()
            id_token = tokens.get("id_token")
            if not isinstance(id_token, str) or not id_token:
                raise ValueError("Missing OIDC ID token")
            header = jwt.get_unverified_header(id_token)
            algorithm = header.get("alg")
            expected = set(endpoints.get("id_token_signing_alg_values_supported", ["RS256"])) & cls.PUBLIC_ALGORITHMS
            if not isinstance(algorithm, str) or algorithm not in expected:
                raise ValueError("Unsupported OIDC signing algorithm")
            jwks_resp = await client.get(endpoints["jwks_uri"])
            jwks_resp.raise_for_status()
            keys = [key for key in jwks_resp.json().get("keys", [])
                    if (not header.get("kid") or key.get("kid") == header["kid"])
                    and key.get("use", "sig") == "sig"
                    and "verify" in key.get("key_ops", ["verify"])
                    and key.get("alg", algorithm) == algorithm
                    and key.get("kty") == ("EC" if algorithm.startswith("ES") else "RSA")]
            if len(keys) != 1:
                raise ValueError("No unique OIDC signing key")
            key = jwt.PyJWK.from_dict(keys[0], algorithm=algorithm).key
            claims = jwt.decode(id_token, key, algorithms=[algorithm], issuer=issuer, audience=client_id,
                                options={"require": ["iss", "sub", "aud", "exp", "iat", "nonce"]})
            if any(isinstance(claims[name], bool) or not isinstance(claims[name], (int, float)) for name in ("exp", "iat")):
                raise ValueError("Invalid OIDC timestamp")
            aud = claims["aud"]
            if isinstance(aud, list) and len(aud) > 1 and claims.get("azp") != client_id:
                raise ValueError("Invalid OIDC authorized party")
            if "azp" in claims and claims["azp"] != client_id:
                raise ValueError("Invalid OIDC authorized party")
            nonce = claims["nonce"]
            if not isinstance(nonce, str) or not nonce.isascii() or not secrets.compare_digest(nonce, transaction["nonce"]):
                raise ValueError("Invalid OIDC nonce")
            sub = claims["sub"]
            if not isinstance(sub, str) or not sub or len(sub) > 255 or not sub.isascii():
                raise ValueError("Invalid OIDC subject")
            userinfo = claims
            if endpoints.get("userinfo_endpoint") and tokens.get("access_token"):
                ui_resp = await client.get(endpoints["userinfo_endpoint"], headers={"Authorization": f"Bearer {tokens['access_token']}"})
                ui_resp.raise_for_status()
                userinfo = ui_resp.json()
                if userinfo.get("sub") != sub:
                    raise ValueError("OIDC UserInfo subject mismatch")
        email = userinfo.get("email", "")
        allowed_emails = cfg.get("oidc_allowed_emails") or []
        if allowed_emails:
            clean_allowed = {a.lower().strip() for a in allowed_emails if isinstance(a, str) and a.strip()}
            if userinfo.get("email_verified") is not True or not isinstance(email, str) or email.lower() not in clean_allowed:
                raise PermissionError("Verified email is not in the allowed SSO whitelist")
        if transaction["expires"] <= time.monotonic():
            raise ValueError("OIDC login expired")
        # All provider/authorization checks precede the first local account write.
        username = cls.principal_username(issuer, sub)
        query = select(AdminUser).where(AdminUser.username == username)
        admin = (await db.execute(query)).scalar_one_or_none()
        if admin is None:
            admin = AdminUser(username=username, password_hash=AuthService.hash_password(secrets.token_urlsafe(48)), is_active=True)
            db.add(admin)
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                admin = (await db.execute(query)).scalar_one_or_none()
                if admin is None:
                    raise
        if not admin.is_active:
            raise PermissionError("SSO admin account is inactive")
        return {"access_token": AuthService.create_access_token(admin.username), "username": admin.username,
                "email": email, "userinfo": userinfo}
