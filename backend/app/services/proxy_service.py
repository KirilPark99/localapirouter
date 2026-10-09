import time
from typing import List, Optional, Dict, Any
from urllib.parse import quote, urlparse, unquote
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import Proxy, ProviderCredential, Provider
from app.schemas.entities import (
    ProxyCreate,
    ProxyUpdate,
    ProxyRead,
    ProxyTestResult,
    ProxyParseResult,
)
from app.core.crypto import encrypt_secret, decrypt_secret
from app.core.http_client import http_client_manager
from datetime import datetime, timezone
import httpx

_CACHED_SERVER_IP: Optional[str] = None
_CACHED_SERVER_IP_TIME: float = 0.0
_COUNTRY_CACHE: Dict[str, tuple[Optional[str], Optional[str]]] = {}

class ProxyService:
    @classmethod
    async def resolve_host_country(cls, host: str) -> tuple[Optional[str], Optional[str]]:
        """Resolves country name and ISO alpha-2 country code for a host or IP."""
        clean_host, _ = cls.sanitize_host_and_port(host, 80)
        if not clean_host or clean_host in ("localhost", "127.0.0.1", "0.0.0.0"):
            return None, None
        if clean_host in _COUNTRY_CACHE:
            return _COUNTRY_CACHE[clean_host]

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(f"https://ip-api.com/json/{clean_host}?fields=status,country,countryCode")
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "success":
                        c_name = data.get("country")
                        c_code = data.get("countryCode")
                        _COUNTRY_CACHE[clean_host] = (c_name, c_code)
                        return c_name, c_code
        except Exception:
            pass
        return None, None
    @staticmethod
    def sanitize_host_and_port(host: str, port: int) -> tuple[str, int]:
        clean_host = (host or "").strip()
        clean_port = port or 8080
        if "://" in clean_host or clean_host.startswith("["):
            parsed = urlparse(clean_host if "://" in clean_host else "//" + clean_host)
            return parsed.hostname or "", parsed.port or clean_port
        if "/" in clean_host:
            clean_host = clean_host.split("/", 1)[0]
        if clean_host.count(":") > 1:
            from ipaddress import IPv6Address
            return str(IPv6Address(clean_host)), clean_port
        if ":" in clean_host:
            h_part, p_part = clean_host.split(":", 1)
            clean_host = h_part
            try:
                clean_port = int(p_part)
            except ValueError:
                pass
        return clean_host, clean_port

    @staticmethod
    def build_proxy_url(proxy: Proxy) -> str:
        username = decrypt_secret(proxy.encrypted_username) if proxy.encrypted_username else ""
        password = decrypt_secret(proxy.encrypted_password) if proxy.encrypted_password else ""
        scheme = (proxy.scheme or "http").lower().strip()
        host, port = ProxyService.sanitize_host_and_port(proxy.host, proxy.port)
        host = f"[{host}]" if ":" in host else host

        if username and password:
            q_user = quote(username, safe="")
            q_pass = quote(password, safe="")
            return f"{scheme}://{q_user}:{q_pass}@{host}:{port}"
        elif username:
            q_user = quote(username, safe="")
            return f"{scheme}://{q_user}@{host}:{port}"
        return f"{scheme}://{host}:{port}"

    @staticmethod
    def validate_proxy_ids(ids: Any) -> List[int]:
        if not isinstance(ids, list) or len(ids) > 16 or any(type(i) is not int or i < 1 for i in ids):
            raise ValueError("Proxy pool must contain at most 16 positive integer IDs")
        if len(ids) != len(set(ids)):
            raise ValueError("Proxy pool contains duplicate IDs")
        return ids

    @classmethod
    async def _pool_proxies(cls, db: AsyncSession, ids: List[int]) -> List[Proxy]:
        cls.validate_proxy_ids(ids)
        rows = {p.id: p for p in (await db.scalars(select(Proxy).where(Proxy.id.in_(ids)))).all()} if ids else {}
        if any(i not in rows for i in ids):
            raise ValueError("A selected pool proxy no longer exists")
        return [rows[i] for i in ids]

    @classmethod
    async def resolve_proxy_pool(cls, db: AsyncSession, ids: List[int]) -> List[str]:
        proxies = await cls._pool_proxies(db, ids)
        if any(not p.enabled for p in proxies):
            raise ValueError("A selected pool proxy is disabled")
        if any(p.scheme not in ("http", "https", "socks5", "socks5h") for p in proxies):
            raise ValueError("Lingling supports HTTP, HTTPS and SOCKS5 proxies")
        if any(not p.host or any(ord(c) <= 32 or ord(c) == 127 for c in p.host)
               or type(p.port) is not int or not 1 <= p.port <= 65535 for p in proxies):
            raise ValueError("Invalid pool proxy address")
        return [cls.build_proxy_url(p) for p in proxies]

    @classmethod
    async def export_pool_fields(cls, db: AsyncSession, fields: dict, *, include_proxies: bool = True) -> dict:
        """Portable endpoints, not numeric IDs belonging to the source database."""
        result = dict(fields)
        ids = result.pop("proxy_ids", [])
        if result.get("transport_mode", "tor") == "tor":
            ids = []  # Dormant/deleted proxies cannot block a Tor profile backup.
            result.pop("proxy_refs", None)
        if include_proxies:
            proxies = await cls._pool_proxies(db, ids)
            result["proxy_refs"] = cls.validate_proxy_refs([{key: getattr(p, key) for key in ("scheme", "host", "port")} for p in proxies])
        else:
            result.pop("proxy_refs", None)
            result["proxy_ids"] = []
        return result

    @staticmethod
    def validate_proxy_refs(refs: Any) -> List[dict]:
        if not isinstance(refs, list) or len(refs) > 16:
            raise ValueError("Invalid portable proxy pool")
        seen = set()
        for ref in refs:
            if (not isinstance(ref, dict) or set(ref) != {"scheme", "host", "port"}
                    or ref["scheme"] not in ("http", "https", "socks5", "socks5h")
                    or not isinstance(ref["host"], str) or not ref["host"].strip()
                    or type(ref["port"]) is not int or not 1 <= ref["port"] <= 65535):
                raise ValueError("Invalid portable proxy reference")
            key = ref["scheme"], ref["host"], ref["port"]
            if key in seen:
                raise ValueError("Portable pool contains duplicate endpoints")
            seen.add(key)
        return refs

    @classmethod
    async def import_pool_fields(cls, db: AsyncSession, fields: dict) -> dict:
        result = dict(fields)
        if "proxy_refs" not in result:
            cls.validate_proxy_ids(result.get("proxy_ids", []))
            return result
        refs = cls.validate_proxy_refs(result.pop("proxy_refs"))
        if "proxy_ids" in result:
            raise ValueError("Invalid portable proxy pool")
        ids = []
        for ref in refs:
            rows = (await db.scalars(select(Proxy).where(Proxy.scheme == ref["scheme"],
                Proxy.host == ref["host"], Proxy.port == ref["port"]))).all()
            if len(rows) != 1:
                raise ValueError("Portable pool proxy is missing or ambiguous; configure matching proxies first")
            ids.append(rows[0].id)
        cls.validate_proxy_ids(ids)
        result["proxy_ids"] = ids
        return result

    @classmethod
    async def get_server_ip(cls) -> str:
        global _CACHED_SERVER_IP, _CACHED_SERVER_IP_TIME
        now = time.time()
        if _CACHED_SERVER_IP and (now - _CACHED_SERVER_IP_TIME) < 300:
            return _CACHED_SERVER_IP

        for test_url in [
            "https://api.ipify.org?format=json",
            "https://httpbin.org/ip",
            "https://icanhazip.com",
        ]:
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.get(test_url)
                    if resp.status_code == 200:
                        if "json" in resp.headers.get("content-type", "") or test_url.endswith("format=json") or "ipify" in test_url or "httpbin" in test_url:
                            try:
                                data = resp.json()
                                ip = data.get("ip") or data.get("origin")
                                if ip:
                                    _CACHED_SERVER_IP = ip.split(",")[0].strip()
                                    _CACHED_SERVER_IP_TIME = now
                                    return _CACHED_SERVER_IP
                            except Exception:
                                pass
                        ip_text = resp.text.strip()
                        if ip_text and len(ip_text) <= 45:
                            _CACHED_SERVER_IP = ip_text
                            _CACHED_SERVER_IP_TIME = now
                            return _CACHED_SERVER_IP
            except Exception:
                continue

        return _CACHED_SERVER_IP or "Unknown"

    @classmethod
    def parse_raw_proxy(cls, raw: str) -> Optional[ProxyParseResult]:
        raw = (raw or "").strip()
        if not raw:
            return None

        # 1. Scheme present: socks5://user:pass@host:port or http://...
        if "://" in raw:
            parsed = urlparse(raw)
            scheme = (parsed.scheme or "http").lower()
            if scheme == "socks5h":
                scheme = "socks5"
            host = parsed.hostname or ""
            port = parsed.port or (1080 if "socks" in scheme else 8080)
            user = unquote(parsed.username) if parsed.username else None
            pwd = unquote(parsed.password) if parsed.password else None
            return ProxyParseResult(
                scheme=scheme,
                host=host,
                port=port,
                username=user,
                password=pwd,
                suggested_name=f"{scheme.upper()}-{host}",
            )

        # 2. Format: user:pass@host:port
        if "@" in raw:
            auth_part, host_part = raw.rsplit("@", 1)
            user, pwd = auth_part.split(":", 1) if ":" in auth_part else (auth_part, None)
            h, p = host_part.split(":", 1) if ":" in host_part else (host_part, "8080")
            port = int(p) if p.isdigit() else 8080
            return ProxyParseResult(
                scheme="http",
                host=h,
                port=port,
                username=user,
                password=pwd,
                suggested_name=f"Proxy-{h}",
            )

        # 3. Colon-separated: host:port:user:pass or host:port
        parts = raw.split(":")
        if len(parts) >= 4:
            host = parts[0]
            port = int(parts[1]) if parts[1].isdigit() else 8080
            user = parts[2]
            pwd = ":".join(parts[3:])  # in case password has colons
            return ProxyParseResult(
                scheme="http",
                host=host,
                port=port,
                username=user,
                password=pwd,
                suggested_name=f"Proxy-{host}",
            )
        elif len(parts) == 2:
            host = parts[0]
            port = int(parts[1]) if parts[1].isdigit() else 8080
            return ProxyParseResult(
                scheme="http",
                host=host,
                port=port,
                username=None,
                password=None,
                suggested_name=f"Proxy-{host}",
            )

        return None

    @classmethod
    async def list_proxies(cls, db: AsyncSession) -> List[ProxyRead]:
        result = await db.execute(
            select(Proxy)
            .options(selectinload(Proxy.credentials).selectinload(ProviderCredential.provider))
            .order_by(Proxy.id.desc())
        )
        proxies = result.scalars().all()
        has_updates = False
        output: List[ProxyRead] = []
        for p in proxies:
            country = p.country
            country_code = p.country_code
            if not country and p.host:
                c_name, c_code = await cls.resolve_host_country(p.host)
                if c_name:
                    p.country = c_name
                    p.country_code = c_code
                    country = c_name
                    country_code = c_code
                    has_updates = True

            assigned = sorted(list({
                c.provider.name
                for c in p.credentials
                if c.provider and c.provider.name
            }))

            output.append(
                ProxyRead(
                    id=p.id,
                    name=p.name,
                    scheme=p.scheme,
                    host=p.host,
                    port=p.port,
                    has_auth=bool(p.encrypted_username or p.encrypted_password),
                    enabled=p.enabled,
                    status=p.status,
                    country=country,
                    country_code=country_code,
                    assigned_providers=assigned,
                    last_check=p.last_check,
                    last_error=p.last_error,
                    created_at=p.created_at,
                )
            )

        if has_updates:
            try:
                await db.commit()
            except Exception:
                pass
        return output

    @classmethod
    async def create_proxy(cls, db: AsyncSession, data: ProxyCreate) -> ProxyRead:
        host, port = cls.sanitize_host_and_port(data.host, data.port)
        scheme = (data.scheme or "http").lower().strip()
        if scheme == "socks5h":
            scheme = "socks5"

        country = data.country
        country_code = data.country_code
        if not country:
            c_name, c_code = await cls.resolve_host_country(host)
            country = c_name
            country_code = c_code

        proxy = Proxy(
            name=data.name.strip(),
            scheme=scheme,
            host=host,
            port=port,
            encrypted_username=encrypt_secret(data.username.strip()) if data.username else None,
            encrypted_password=encrypt_secret(data.password.strip()) if data.password else None,
            enabled=data.enabled,
            status="UNTESTED",
            country=country,
            country_code=country_code,
        )
        db.add(proxy)
        await db.commit()
        await db.refresh(proxy)
        return ProxyRead(
            id=proxy.id,
            name=proxy.name,
            scheme=proxy.scheme,
            host=proxy.host,
            port=proxy.port,
            has_auth=bool(proxy.encrypted_username or proxy.encrypted_password),
            enabled=proxy.enabled,
            status=proxy.status,
            country=proxy.country,
            country_code=proxy.country_code,
            assigned_providers=[],
            last_check=proxy.last_check,
            last_error=proxy.last_error,
            created_at=proxy.created_at,
        )

    @staticmethod
    async def _close_lingling_workers() -> None:
        from app.modules.loader import ModuleLoader
        adapter = ModuleLoader.get_adapter("lingling")
        if adapter:
            # ponytail: close all Lingling workers; index dependencies if pool counts grow.
            await adapter.close()

    @classmethod
    async def update_proxy(cls, db: AsyncSession, proxy_id: int, data: ProxyUpdate) -> Optional[ProxyRead]:
        result = await db.execute(
            select(Proxy)
            .options(selectinload(Proxy.credentials).selectinload(ProviderCredential.provider))
            .where(Proxy.id == proxy_id)
        )
        proxy = result.scalar_one_or_none()
        if not proxy:
            return None

        if data.name is not None:
            proxy.name = data.name.strip()
        if data.scheme is not None:
            s = data.scheme.lower().strip()
            proxy.scheme = "socks5" if s == "socks5h" else s
        host_changed = False
        if data.host is not None:
            h, p = cls.sanitize_host_and_port(data.host, data.port or proxy.port)
            if h != proxy.host:
                host_changed = True
            proxy.host = h
            proxy.port = p
        if data.port is not None:
            proxy.port = data.port
        if data.username is not None:
            proxy.encrypted_username = encrypt_secret(data.username.strip()) if data.username else None
        if data.password is not None:
            proxy.encrypted_password = encrypt_secret(data.password.strip()) if data.password else None
        if data.enabled is not None:
            proxy.enabled = data.enabled
        if data.country is not None:
            proxy.country = data.country
        if data.country_code is not None:
            proxy.country_code = data.country_code
        elif host_changed and data.country is None:
            c_name, c_code = await cls.resolve_host_country(proxy.host)
            if c_name:
                proxy.country = c_name
                proxy.country_code = c_code

        assigned = sorted(list({
            c.provider.name
            for c in proxy.credentials
            if c.provider and c.provider.name
        }))
        await db.commit()
        await db.refresh(proxy)
        if any(getattr(data, key) is not None for key in ("scheme", "host", "port", "username", "password", "enabled")):
            await cls._close_lingling_workers()

        return ProxyRead(
            id=proxy.id,
            name=proxy.name,
            scheme=proxy.scheme,
            host=proxy.host,
            port=proxy.port,
            has_auth=bool(proxy.encrypted_username or proxy.encrypted_password),
            enabled=proxy.enabled,
            status=proxy.status,
            country=proxy.country,
            country_code=proxy.country_code,
            assigned_providers=assigned,
            last_check=proxy.last_check,
            last_error=proxy.last_error,
            created_at=proxy.created_at,
        )

    @classmethod
    async def delete_proxy(cls, db: AsyncSession, proxy_id: int) -> bool:
        result = await db.execute(select(Proxy).where(Proxy.id == proxy_id))
        proxy = result.scalar_one_or_none()
        if not proxy:
            return False
        await db.delete(proxy)
        await db.commit()
        await cls._close_lingling_workers()
        return True

    @classmethod
    def _format_proxy_error(cls, exc: Exception, server_ip: str, host: str, port: int) -> tuple[str, str]:
        err_str = str(exc)
        low_err = err_str.lower()

        if "407" in err_str or "proxy authentication required" in low_err:
            msg = f"Error 407: Proxy server rejected authentication."
            details = (
                f"Proxy {host}:{port} returned HTTP 407 (Proxy Authentication Required).\n"
                f"Possible causes:\n"
                f"1) Invalid username or password.\n"
                f"2) Proxy provider requires IP Whitelist authorization.\n"
                f"Add your server's outbound IP ({server_ip}) to the whitelist in your proxy dashboard."
            )
            return msg, details

        if "rejected by the socks5 server" in low_err or "authentication failure" in low_err or "socks5" in low_err and "reject" in low_err:
            msg = "SOCKS5 server rejected credentials (Auth failed)."
            details = (
                f"SOCKS5 proxy {host}:{port} rejected authentication handshake.\n"
                f"Possible causes:\n"
                f"1) Invalid username or password.\n"
                f"2) Proxy provider requires IP Whitelist authorization.\n"
                f"Add your server's outbound IP ({server_ip}) to the whitelist in your proxy dashboard."
            )
            return msg, details

        if "connecttimeout" in low_err or "timed out" in low_err or "timeout" in low_err:
            msg = f"Connection timeout to {host}:{port}."
            details = f"Proxy server {host}:{port} did not respond within 12 seconds. Verify proxy is active and port is open."
            return msg, details

        if "connectionrefused" in low_err or "connecterror" in low_err or "refused" in low_err:
            msg = f"Connection refused: {host}:{port}."
            details = f"Server reset connection or port {port} is closed on host {host}."
            return msg, details

        msg = f"Connection failed: {err_str[:120]}"
        details = f"Full error: {err_str}"
        return msg, details

    @classmethod
    async def _execute_proxy_probe(cls, proxy_url: str, host: str, port: int) -> ProxyTestResult:
        server_ip = await cls.get_server_ip()
        t0 = time.perf_counter()

        endpoints = [
            ("https://api.ipify.org?format=json", "json", "ip"),
            ("https://httpbin.org/ip", "json", "origin"),
            ("https://icanhazip.com", "text", ""),
        ]

        last_error_exc = None
        for test_url, resp_type, key_name in endpoints:
            try:
                client = await http_client_manager.get_client(proxy_url=proxy_url, timeout=12.0, force_fresh=True)
                resp = await client.get(test_url)
                latency_ms = round((time.perf_counter() - t0) * 1000, 1)

                if resp.status_code == 200:
                    outbound_ip = None
                    if resp_type == "json":
                        try:
                            data = resp.json()
                            outbound_ip = data.get(key_name)
                        except Exception:
                            pass
                    if not outbound_ip:
                        outbound_ip = resp.text.strip().split(",")[0].strip()

                    c_name, c_code = await cls.resolve_host_country(outbound_ip or host)
                    return ProxyTestResult(
                        success=True,
                        latency_ms=latency_ms,
                        message=f"Connection successful! Proxy IP: {outbound_ip} ({latency_ms} ms)",
                        ip=outbound_ip,
                        server_ip=server_ip,
                        country=c_name,
                        country_code=c_code,
                        details=f"Proxy successfully tunneled HTTPS traffic. Outbound IP changed from {server_ip} to {outbound_ip}.",
                    )
                else:
                    if resp.status_code == 407:
                        raise httpx.ProxyError(f"HTTP 407 Proxy Authentication Required")
                    last_error_exc = RuntimeError(f"HTTP {resp.status_code}")
            except Exception as e:
                last_error_exc = e
                # If authentication failed, no need to retry other endpoints
                if "407" in str(e) or "rejected" in str(e).lower():
                    break

        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        msg, details = cls._format_proxy_error(last_error_exc or Exception("Unknown error"), server_ip, host, port)
        return ProxyTestResult(
            success=False,
            latency_ms=latency_ms,
            message=msg,
            server_ip=server_ip,
            details=details,
        )

    @classmethod
    async def test_proxy(cls, db: AsyncSession, proxy_id: int) -> ProxyTestResult:
        result = await db.execute(select(Proxy).where(Proxy.id == proxy_id))
        proxy = result.scalar_one_or_none()
        if not proxy:
            return ProxyTestResult(success=False, latency_ms=0, message="Proxy not found")

        proxy_url = cls.build_proxy_url(proxy)
        res = await cls._execute_proxy_probe(proxy_url, proxy.host, proxy.port)

        if res.success:
            proxy.status = "HEALTHY"
            proxy.last_error = None
            if res.country and not proxy.country:
                proxy.country = res.country
                proxy.country_code = res.country_code
        else:
            proxy.status = "ERROR"
            proxy.last_error = res.details or res.message
        proxy.last_check = datetime.now(timezone.utc)
        await db.commit()
        return res

    @classmethod
    async def test_raw_proxy(cls, data: ProxyCreate) -> ProxyTestResult:
        host, port = cls.sanitize_host_and_port(data.host, data.port)
        scheme = (data.scheme or "http").lower().strip()
        if scheme == "socks5h":
            scheme = "socks5"

        dummy = Proxy(
            name=data.name or "Test",
            scheme=scheme,
            host=host,
            port=port,
            encrypted_username=encrypt_secret(data.username.strip()) if data.username else None,
            encrypted_password=encrypt_secret(data.password.strip()) if data.password else None,
        )
        proxy_url = cls.build_proxy_url(dummy)
        return await cls._execute_proxy_probe(proxy_url, host, port)
