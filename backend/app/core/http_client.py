from typing import Dict, Optional, Tuple
from urllib.parse import urlparse, unquote
import httpx
from httpx_socks import AsyncProxyTransport, ProxyType

class HttpClientManager:
    """Manages cached httpx.AsyncClient pools per proxy and direct connection."""
    def __init__(self):
        self._clients: Dict[str, httpx.AsyncClient] = {}

    def _create_proxy_transport(self, proxy_url: str) -> Tuple[Optional[AsyncProxyTransport], Optional[str]]:
        clean_url = proxy_url.strip()
        parsed = urlparse(clean_url)
        scheme = (parsed.scheme or "http").lower()
        host = parsed.hostname or ""
        port = parsed.port or (1080 if "socks" in scheme else 8080)
        username = unquote(parsed.username) if parsed.username else None
        password = unquote(parsed.password) if parsed.password else None

        if scheme in ("socks5", "socks5h"):
            # Use AsyncProxyTransport with SOCKS5 and remote DNS resolution (rdns=True)
            transport = AsyncProxyTransport(
                proxy_type=ProxyType.SOCKS5,
                proxy_host=host,
                proxy_port=port,
                username=username,
                password=password,
                rdns=True,
            )
            return transport, None
        elif scheme in ("socks4", "socks4a"):
            transport = AsyncProxyTransport(
                proxy_type=ProxyType.SOCKS4,
                proxy_host=host,
                proxy_port=port,
                username=username,
                password=password,
                rdns=True,
            )
            return transport, None
        else:
            # Keep TLS-to-proxy and percent-encoded credentials intact.
            return None, clean_url

    async def get_client(
        self,
        proxy_url: Optional[str] = None,
        timeout: float = 60.0,
        force_fresh: bool = False,
    ) -> httpx.AsyncClient:
        key = f"{proxy_url or 'direct'}::{timeout}"
        if not force_fresh and key in self._clients and not self._clients[key].is_closed:
            return self._clients[key]

        timeout_config = httpx.Timeout(timeout, connect=15.0, read=timeout, write=15.0)

        if proxy_url:
            transport, proxy_str = self._create_proxy_transport(proxy_url)
            if transport:
                client = httpx.AsyncClient(
                    transport=transport,
                    timeout=timeout_config,
                    follow_redirects=True,
                )
            else:
                client = httpx.AsyncClient(
                    proxy=proxy_str,
                    timeout=timeout_config,
                    follow_redirects=True,
                )
        else:
            client = httpx.AsyncClient(
                timeout=timeout_config,
                follow_redirects=True,
            )

        if not force_fresh:
            self._clients[key] = client
        return client

    async def close_client(self, proxy_url: Optional[str] = None, timeout: float = 60.0):
        key = f"{proxy_url or 'direct'}::{timeout}"
        if key in self._clients:
            client = self._clients.pop(key)
            if not client.is_closed:
                await client.aclose()

    async def close_all(self):
        """Close all pooled clients gracefully."""
        for client in self._clients.values():
            if not client.is_closed:
                await client.aclose()
        self._clients.clear()

http_client_manager = HttpClientManager()
