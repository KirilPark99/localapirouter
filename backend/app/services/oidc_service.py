"""OpenID Connect (OIDC) Service for Single Sign-On (SSO).

Supports Google, Keycloak, Okta, Authentik, Azure AD, and any standard OIDC provider.
"""
import secrets
import logging
import urllib.parse
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.security.registry import GuardrailRegistry
from app.services.auth_service import AuthService
from app.core.config import settings

logger = logging.getLogger("app.services.oidc")


class OidcService:
    @classmethod
    async def get_oidc_endpoints(cls, issuer: str) -> Dict[str, str]:
        """Fetch well-known OIDC endpoints or fall back to conventional routes."""
        clean_issuer = issuer.rstrip("/")
        well_known_url = f"{clean_issuer}/.well-known/openid-configuration"

        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(well_known_url)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "authorization_endpoint": data.get("authorization_endpoint", f"{clean_issuer}/authorize"),
                        "token_endpoint": data.get("token_endpoint", f"{clean_issuer}/token"),
                        "userinfo_endpoint": data.get("userinfo_endpoint", f"{clean_issuer}/userinfo"),
                        "jwks_uri": data.get("jwks_uri", f"{clean_issuer}/jwks"),
                    }
        except Exception as e:
            logger.debug(f"Could not discover OIDC configuration at {well_known_url}: {e}")

        # Fallback to standard convention
        return {
            "authorization_endpoint": f"{clean_issuer}/authorize",
            "token_endpoint": f"{clean_issuer}/token",
            "userinfo_endpoint": f"{clean_issuer}/userinfo",
            "jwks_uri": f"{clean_issuer}/jwks",
        }

    @classmethod
    async def get_authorization_url(
        cls, db: AsyncSession, redirect_uri: str, state: Optional[str] = None
    ) -> Optional[str]:
        cfg = await GuardrailRegistry.get_security_config(db)
        if not cfg.get("oidc_enabled"):
            return None

        issuer = cfg.get("oidc_issuer", "").strip()
        client_id = cfg.get("oidc_client_id", "").strip()
        if not issuer or not client_id:
            logger.warning("OIDC enabled but issuer or client_id is missing")
            return None

        endpoints = await cls.get_oidc_endpoints(issuer)
        auth_url = endpoints["authorization_endpoint"]
        scopes = " ".join(cfg.get("oidc_scopes") or ["openid", "profile", "email"])
        state_token = state or secrets.token_urlsafe(24)

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scopes,
            "state": state_token,
            "prompt": "select_account",
        }
        return f"{auth_url}?{urllib.parse.urlencode(params)}"

    @classmethod
    async def exchange_code(
        cls, db: AsyncSession, code: str, redirect_uri: str
    ) -> Dict[str, Any]:
        cfg = await GuardrailRegistry.get_security_config(db)
        if not cfg.get("oidc_enabled"):
            raise ValueError("OIDC authentication is not enabled")

        issuer = cfg.get("oidc_issuer", "").strip()
        client_id = cfg.get("oidc_client_id", "").strip()
        client_secret = cfg.get("oidc_client_secret", "").strip()

        if not issuer or not client_id:
            raise ValueError("OIDC configuration incomplete")

        endpoints = await cls.get_oidc_endpoints(issuer)
        token_endpoint = endpoints["token_endpoint"]

        # Exchange code for tokens
        token_payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(token_endpoint, data=token_payload)
            if resp.status_code != 200:
                logger.error(f"OIDC token exchange failed: {resp.text}")
                raise ValueError("Failed to exchange authorization code with identity provider")

            tokens = resp.json()

        access_token = tokens.get("access_token")
        id_token = tokens.get("id_token")

        userinfo: Dict[str, Any] = {}
        # Fetch userinfo if endpoint exists and access_token is present
        userinfo_endpoint = endpoints.get("userinfo_endpoint")
        if userinfo_endpoint and access_token:
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    ui_resp = await client.get(
                        userinfo_endpoint,
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    if ui_resp.status_code == 200:
                        userinfo = ui_resp.json()
            except Exception as e:
                logger.debug(f"Userinfo request failed: {e}")

        email = userinfo.get("email") or ""
        sub = userinfo.get("sub") or ""
        username = email or sub or "sso_user"

        # Check whitelist if configured
        allowed_emails = cfg.get("oidc_allowed_emails") or []
        if allowed_emails:
            clean_allowed = [a.lower().strip() for a in allowed_emails if a.strip()]
            if clean_allowed and email.lower() not in clean_allowed and sub not in clean_allowed:
                raise PermissionError(f"User '{username}' is not in the allowed SSO whitelist")

        # Create session token
        jwt_token = AuthService.create_access_token(username)
        return {
            "access_token": jwt_token,
            "username": username,
            "email": email,
            "userinfo": userinfo,
        }
