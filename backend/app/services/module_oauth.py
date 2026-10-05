"""Short-lived browser OAuth sessions; provider tokens never leave the backend."""
import asyncio
import base64
import hashlib
import secrets
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from fastapi import HTTPException

from app.core.http_client import http_client_manager
from modules.agy_cli.handler import AGY_CLIENT_ID, AGY_CLIENT_SECRET, GOOGLE_OAUTH_TOKEN_URL
from modules.codex_cli.handler import CODEX_CLIENT_ID, CODEX_TOKEN_URL, _decode_jwt_payload
from modules.grok_builder_cli.handler import GROK_CLIENT_ID, GROK_TOKEN_URL


CONFIG = {
    "agy_cli": {
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth", "token": GOOGLE_OAUTH_TOKEN_URL,
        "client_id": AGY_CLIENT_ID, "client_secret": AGY_CLIENT_SECRET,
        "scope": " ".join("https://www.googleapis.com/auth/" + name for name in (
            "cloud-platform", "userinfo.email", "userinfo.profile", "cclog", "experimentsandconfigs")),
        "host": "127.0.0.1", "port": 0, "path": "/callback", "pkce_bytes": 0,
        "extra": {"access_type": "offline", "prompt": "consent"},
    },
    "codex_cli": {
        "authorize": "https://auth.openai.com/oauth/authorize", "token": CODEX_TOKEN_URL,
        "client_id": CODEX_CLIENT_ID, "scope": "openid profile email offline_access",
        "host": "localhost", "port": 1455, "path": "/auth/callback", "pkce_bytes": 32,
        "extra": {"id_token_add_organizations": "true", "codex_cli_simplified_flow": "true",
                  "originator": "codex_cli_rs", "prompt": "login"},
    },
    "grok_builder_cli": {
        "authorize": "https://auth.x.ai/oauth2/authorize", "token": GROK_TOKEN_URL,
        "client_id": GROK_CLIENT_ID, "scope": "openid profile email offline_access grok-cli:access",
        "host": "127.0.0.1", "port": 56122, "path": "/callback", "pkce_bytes": 96, "extra": {},
    },
}
TTL = 600


@dataclass
class OAuthSession:
    module_id: str
    owner: str
    proxy_id: int | None
    proxy_url: str | None = field(repr=False)
    state: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)
    verifier: str = field(default="", repr=False)
    redirect_uri: str = ""
    auth_url: str = ""
    status: str = "pending"
    message: str = ""
    tokens: dict = field(default_factory=dict, repr=False)
    expires_at: float = field(default_factory=lambda: time.monotonic() + TTL)
    server: asyncio.Server | None = field(default=None, repr=False)
    expiry_task: asyncio.Task | None = field(default=None, repr=False)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    def public(self):
        return {"status": self.status, "message": self.message,
                "expires_in": max(0, int(self.expires_at - time.monotonic()))}


# ponytail: one API worker; use shared encrypted storage for multi-worker deployments.
sessions: dict[str, OAuthSession] = {}
# ponytail: serialize local starts; shared coordination is needed for multiple workers.
start_lock = asyncio.Lock()


def discard(session_id: str):
    """Immediate cleanup, only while holding session.lock or when it is idle."""
    session = sessions.pop(session_id, None)
    if session:
        if session.server:
            session.server.close()
        if session.expiry_task and session.expiry_task is not asyncio.current_task():
            session.expiry_task.cancel()
        session.status = "cancelled"
        session.expires_at = 0
        session.tokens.clear()
        session.verifier = ""
        session.proxy_url = None


async def cancel(session_id: str):
    session = sessions.get(session_id)
    if session:
        async with session.lock:
            discard(session_id)


def get_session(session_id: str, module_id: str, owner: str) -> OAuthSession:
    session = sessions.get(session_id)
    if not session or session.module_id != module_id or session.owner != owner:
        raise HTTPException(404, "OAuth session not found")
    if session.expires_at <= time.monotonic():
        if not session.lock.locked():
            discard(session_id)
        raise HTTPException(410, "OAuth session expired; start again")
    return session


async def start(module_id: str, owner: str, proxy_id: int | None, proxy_url: str | None):
    async with start_lock:
        return await _start(module_id, owner, proxy_id, proxy_url)


async def _start(module_id: str, owner: str, proxy_id: int | None, proxy_url: str | None):
    if module_id not in CONFIG:
        raise HTTPException(400, "Browser OAuth is not supported for this module")
    config = CONFIG[module_id]
    if not config["client_id"] or (module_id == "agy_cli" and not config.get("client_secret")):
        raise HTTPException(503, "OAuth application credentials are not configured; set the module's OAuth environment variables")
    for sid, existing in list(sessions.items()):
        if existing.expires_at <= time.monotonic() or (existing.owner == owner and existing.module_id == module_id):
            await cancel(sid)
    if len(sessions) >= 32:
        raise HTTPException(429, "Too many pending OAuth sessions")
    session = OAuthSession(module_id, owner, proxy_id, proxy_url)
    session_id = secrets.token_urlsafe(32)
    port = config["port"]
    try:
        session.server = await asyncio.start_server(
            lambda reader, writer: loopback(session, reader, writer), "127.0.0.1", port, limit=8192)
        port = session.server.sockets[0].getsockname()[1]
    except OSError:
        if not port:
            raise HTTPException(503, "Cannot open OAuth callback listener") from None
        # Keep the registered redirect on a busy fixed port; the user can paste its URL.
    session.redirect_uri = f"http://{config['host']}:{port}{config['path']}"
    params = {"response_type": "code", "client_id": config["client_id"],
              "redirect_uri": session.redirect_uri, "scope": config["scope"],
              "state": session.state, **config["extra"]}
    if config["pkce_bytes"]:
        session.verifier = secrets.token_urlsafe(config["pkce_bytes"])
        challenge = base64.urlsafe_b64encode(hashlib.sha256(session.verifier.encode()).digest()).decode().rstrip("=")
        params.update(code_challenge=challenge, code_challenge_method="S256")
    session.auth_url = config["authorize"] + "?" + urlencode(params)
    sessions[session_id] = session

    async def expire():
        await asyncio.sleep(TTL)
        await cancel(session_id)

    session.expiry_task = asyncio.create_task(expire())
    return {"session_id": session_id, "auth_url": session.auth_url,
            "loopback": session.server is not None, **session.public()}


async def exchange(session: OAuthSession, callback_url: str):
    """Validate the complete callback, then perform a single token exchange."""
    try:
        url = urlsplit(callback_url.strip())
        expected = urlsplit(session.redirect_uri)
        query = parse_qs(url.query, keep_blank_values=True, max_num_fields=20)
        same_target = (url.scheme, url.netloc, url.path) == (expected.scheme, expected.netloc, expected.path)
        states = query.get("state", [])
        if not same_target or url.fragment or len(states) != 1 or not secrets.compare_digest(states[0], session.state):
            raise ValueError
    except (ValueError, TypeError):
        raise HTTPException(400, "Callback URL or OAuth state does not match this session") from None
    async with session.lock:
        if session.expires_at <= time.monotonic():
            raise HTTPException(410, "OAuth session expired; start again")
        if session.status != "pending":
            raise HTTPException(409, "OAuth callback already processed; start again if needed")
        if "error" in query:
            session.status, session.message = "error", "Authorization was denied by the provider; start again"
        else:
            codes = query.get("code", [])
            if len(codes) != 1 or not codes[0] or len(codes[0]) > 4096:
                raise HTTPException(400, "Callback URL must contain one authorization code")
            config = CONFIG[session.module_id]
            data = {"grant_type": "authorization_code", "client_id": config["client_id"],
                    "code": codes[0], "redirect_uri": session.redirect_uri}
            if session.verifier:
                data["code_verifier"] = session.verifier
            if config.get("client_secret"):
                data["client_secret"] = config["client_secret"]
            headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
            if session.module_id == "agy_cli":
                headers["User-Agent"] = "antigravity/cli/1.1.5 (aidev_client; os_type=darwin; arch=arm64; auth_method=consumer)"
            try:
                client = await http_client_manager.get_client(proxy_url=session.proxy_url, timeout=20)
                response = await client.post(config["token"], data=data, headers=headers, follow_redirects=False)
                if response.status_code != 200:
                    raise ValueError(f"OAuth token exchange rejected (HTTP {response.status_code}); start again")
                tokens = response.json()
                access = tokens.get("access_token")
                if not isinstance(access, str) or not access or not access.isascii() or any(c.isspace() for c in access):
                    raise ValueError("Provider returned an invalid access token; start again")
                refresh = tokens.get("refresh_token")
                if refresh is not None and (not isinstance(refresh, str) or not refresh.isascii()):
                    raise ValueError("Provider returned an invalid refresh token; start again")
                fields = {"auto_detect_local": "false", "auth_json": "", "access_token": access,
                          "refresh_token": refresh or ""}
                claims = _decode_jwt_payload(tokens.get("id_token") or "")
                if session.module_id == "codex_cli":
                    auth = claims.get("https://api.openai.com/auth") or {}
                    fields["account_id"] = auth.get("chatgpt_account_id", "") if isinstance(auth, dict) else ""
                elif session.module_id == "grok_builder_cli":
                    fields.update(key="", email=claims.get("email", ""))
                if session.expires_at <= time.monotonic() or session.status != "pending":
                    raise HTTPException(410, "OAuth session expired or cancelled")
                session.tokens = fields
                session.status, session.message = "authorized", "Authorization complete; save the profile"
            except (httpx.HTTPError, ValueError, TypeError, AttributeError):
                # Never expose provider bodies, codes, tokens, or proxy credentials in errors.
                session.status, session.message = "error", "OAuth token exchange failed; check the selected proxy and start again"
        if session.server:
            session.server.close()
        session.verifier = ""
        return session.public()


async def loopback(session: OAuthSession, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    code = 200
    message = "Авторизация завершена. Вернитесь в MyAIrouter и сохраните профиль."
    try:
        header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
        method, target, _ = header.decode("ascii").split("\r\n", 1)[0].split(" ", 2)
        parsed = urlsplit(target)
        if method != "GET" or parsed.scheme or parsed.netloc or parsed.path != urlsplit(session.redirect_uri).path:
            raise HTTPException(404, "Not found")
        redirect = urlsplit(session.redirect_uri)
        origin = f"{redirect.scheme}://{redirect.netloc}"
        result = await exchange(session, origin + target)
        if result["status"] == "error":
            code, message = 400, "Авторизация не завершена. Вернитесь в MyAIrouter и начните заново."
    except HTTPException as exc:
        code, message = exc.status_code, "Неверный или уже использованный OAuth callback. Вернитесь в MyAIrouter."
    except (ValueError, UnicodeError, asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        code, message = 400, "Неверный запрос."
    finally:
        body = ("<!doctype html><meta charset='utf-8'><title>MyAIrouter OAuth</title><p>" + message + "</p>").encode()
        writer.write(f"HTTP/1.1 {code} Result\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {len(body)}\r\nCache-Control: no-store\r\nReferrer-Policy: no-referrer\r\nConnection: close\r\n\r\n".encode() + body)
        try:
            await writer.drain()
        except ConnectionError:
            pass
        writer.close()
        await writer.wait_closed()


async def close_all():
    async with start_lock:
        for session_id in list(sessions):
            await cancel(session_id)
