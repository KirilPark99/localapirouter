"""Free, no-API-key web search via DuckDuckGo's HTML 'lite' endpoint.

Used as a LAST-RESORT fallback search provider when no paid/credentialed
search provider (Serper, Brave, Tavily, etc.) is configured or available.
"""
import re
import html
import logging
import urllib.parse
import ipaddress
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("app.services.search.duckduckgo_lite")

DUCKDUCKGO_LITE_URL = "https://lite.duckduckgo.com/lite/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

ANCHOR_RE = re.compile(
    r"<a\b([^>]*?class=['\"][^'\"]*result-link[^'\"]*['\"][^>]*)>([\s\S]{0,512}?)<\/a>",
    re.IGNORECASE,
)
HREF_RE = re.compile(r"href=['\"]([^'\"]+)['\"]", re.IGNORECASE)
SNIPPET_RE = re.compile(
    r"<td\b[^>]*?class=['\"][^'\"]*result-snippet[^'\"]*['\"][^>]*>([\s\S]{0,2048}?)<\/td>",
    re.IGNORECASE,
)

MAX_HTML_BYTES = 256 * 1024  # 256 KB safety cap to prevent ReDoS on abnormal responses


def decode_entities(text: str) -> str:
    """Decode HTML entities safely."""
    if not text:
        return ""
    return html.unescape(text)


def strip_tags(html_text: str) -> str:
    """Remove HTML tags safely while preserving decoded text."""
    if not html_text:
        return ""
    text = decode_entities(html_text)
    # Remove HTML tags in a loop until clean
    prev = ""
    while prev != text:
        prev = text
        text = re.sub(r"<[^>]*>", "", text)
    # Remove unclosed trailing tag
    text = re.sub(r"<[^>]*$", "", text)
    return " ".join(text.split()).strip()


def is_safe_public_url(url_str: str) -> bool:
    """SSRF Guard: Verify that URL is http/https and does not resolve to private/loopback IPs."""
    if not url_str or not re.match(r"^https?://", url_str, re.IGNORECASE):
        return False

    try:
        parsed = urllib.parse.urlparse(url_str)
        hostname = (parsed.hostname or "").strip().lower()
        if not hostname:
            return False

        # Block localhost / internal hostnames
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return False
        if hostname.endswith(".local") or hostname.endswith(".internal"):
            return False

        # Check IP ranges if hostname is an IP
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
                return False
        except ValueError:
            # Not an IP literal, valid hostname
            pass

        return True
    except Exception:
        return False


def resolve_result_url(href: str) -> str:
    """Resolve redirect wrappers (e.g. //duckduckgo.com/l/?uddg=...) to real target URLs."""
    if not href:
        return ""

    candidate = href
    uddg_match = re.search(r"[?&]uddg=([^&]+)", href)
    if uddg_match:
        try:
            candidate = urllib.parse.unquote(uddg_match.group(1))
        except Exception:
            candidate = href
    elif href.startswith("//"):
        candidate = f"https:{href}"

    return candidate if is_safe_public_url(candidate) else ""


def parse_duckduckgo_lite(raw_html: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Parse DuckDuckGo Lite HTML response into list of {title, url, snippet}."""
    if not raw_html:
        return []

    capped_html = raw_html[:MAX_HTML_BYTES]
    anchors = list(ANCHOR_RE.finditer(capped_html))
    snippets = list(SNIPPET_RE.finditer(capped_html))

    results: List[Dict[str, str]] = []

    for i, a_match in enumerate(anchors):
        if len(results) >= max_results:
            break

        tag_attrs = a_match.group(1)
        raw_title = a_match.group(2)

        href_match = HREF_RE.search(tag_attrs)
        if not href_match:
            continue

        raw_href = href_match.group(1)
        url = resolve_result_url(raw_href)
        if not url:
            continue

        title = strip_tags(raw_title)
        snippet = ""
        if i < len(snippets):
            snippet = strip_tags(snippets[i].group(1))

        results.append(
            {
                "title": title or url,
                "url": url,
                "snippet": snippet,
            }
        )

    return results


async def search_duckduckgo_lite(
    query: str,
    max_results: int = 5,
    timeout: float = 10.0,
) -> List[Dict[str, str]]:
    """Execute a free, anonymous search query on DuckDuckGo Lite endpoint."""
    clean_query = query.strip()
    if not clean_query:
        return []

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://lite.duckduckgo.com/",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {"q": clean_query}

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.post(DUCKDUCKGO_LITE_URL, data=data, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"DuckDuckGo lite search returned HTTP {resp.status_code}")
                return []
            return parse_duckduckgo_lite(resp.text, max_results=max_results)
    except Exception as e:
        logger.warning(f"DuckDuckGo lite search failed: {e}")
        return []
