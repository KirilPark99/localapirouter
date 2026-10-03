import os
import json
import time
import uuid
import re
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple

import httpx
from app.modules.base import BaseModuleAdapter, ModuleExecutionContext
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
)
from app.adapters.base import DiscoveredModelData

logger = logging.getLogger("app.modules.notion_web")

BASE_URL = "https://app.notion.com"
NOTION_URL = f"{BASE_URL}/api/v3/runInferenceTranscript"
NOTION_SPACES_URL = f"{BASE_URL}/api/v3/getSpaces"
NOTION_AVAILABLE_MODELS_URL = f"{BASE_URL}/api/v3/getAvailableModels"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)
NOTION_CLIENT_VERSION = "23.13.20261002.1401"

REVERSE_CODENAME_TO_ID: Dict[str, str] = {
    # OpenAI
    "omniberry-sundae": "gpt-6.1-sol",
    "orchid-muffin": "gpt-5.6-terra",
    "omodi": "gpt-6-luna",
    "olive-jellyroll": "gpt-5.6-luna",
    "oatmeal-cookie": "gpt-5.2",
    "oval-kumquat-medium": "gpt-5.4",
    "opal-quince-medium": "gpt-5.5",
    "oregon-grape-medium": "gpt-5.4-mini",
    "otaheite-apple-medium": "gpt-5.4-nano",
    "orlando-quinn": "gpt-6-astra",

    # Anthropic
    "albuquerque-quinn": "opus-5.5",
    "almond-croissant-low": "sonnet-4.6",
    "angel-cake-high": "sonnet-5",
    "achira-donut": "sonnet-5.5",
    "avocado-froyo-medium": "opus-4.6",
    "apricot-sorbet-high": "opus-4.7",
    "ambrosia-tart-high": "opus-4.8",
    "agave-flan": "opus-5",
    "anthropic-haiku-4.5": "haiku-4.5",
    "assam-chai": "fable-5.1",
    "acai-budino-high": "fable-5",

    # Google Gemini
    "vertex-gemini-3.5-flash": "gemini-3.5-flash",
    "vertex-gemini-3.6-flash": "gemini-3.6-flash",
    "grapefruit-zeppole": "gemini-3.7-flash",
    "galette-medium-thinking": "gemini-3.1-pro",
    "gingerbread": "gemini-3-flash",

    # DeepSeek
    "baseten-deepseek-v4-pro": "deepseek-v4-pro",
    "baseten-deepseek-v4-flash": "deepseek-v4-flash",
    "baseten-deepseek-v4.1-flash": "deepseek-v4.1-flash",

    # Moonshot Kimi
    "fireworks-kimi-k3": "kimi-k3",

    # Zhipu GLM
    "baseten-glm-5.2": "glm-5.2",
    "baseten-glm-5.3": "glm-5.3",
    "baseten-glm-5.3-flash": "glm-5.3-flash",

    # xAI Grok
    "soursop-shortcake": "grok-4.6",
    "strawberry-whoopiepie": "grok-4.5",
    "xigua-mochi-medium": "grok-4.3",
    "xinomavro-cake": "grok-build-0.1",
}

NOTION_CODENAMES: Dict[str, str] = {
    # Notion AI Default
    "notion-ai": "",
    "default": "",
    "auto": "",

    # OpenAI / GPT
    "gpt-6.1-sol": "omniberry-sundae",
    "gpt-6-1-sol": "omniberry-sundae",
    "omniberry-sundae": "omniberry-sundae",

    "gpt-5.6-terra": "orchid-muffin",
    "gpt-5-6-terra": "orchid-muffin",
    "orchid-muffin": "orchid-muffin",

    "gpt-6-luna": "omodi",
    "gpt-6.0-luna": "omodi",
    "omodi": "omodi",

    "gpt-5.6-luna": "olive-jellyroll",
    "gpt-5-6-luna": "olive-jellyroll",
    "olive-jellyroll": "olive-jellyroll",

    "gpt-5.2": "oatmeal-cookie",
    "gpt-5-2": "oatmeal-cookie",
    "oatmeal-cookie": "oatmeal-cookie",

    "gpt-5.4": "oval-kumquat-medium",
    "gpt-5-4": "oval-kumquat-medium",
    "oval-kumquat-medium": "oval-kumquat-medium",

    "gpt-5.5": "opal-quince-medium",
    "gpt-5-5": "opal-quince-medium",
    "opal-quince-medium": "opal-quince-medium",

    "gpt-5.4-mini": "oregon-grape-medium",
    "gpt-5-4-mini": "oregon-grape-medium",
    "oregon-grape-medium": "oregon-grape-medium",

    "gpt-5.4-nano": "otaheite-apple-medium",
    "gpt-5-4-nano": "otaheite-apple-medium",
    "otaheite-apple-medium": "otaheite-apple-medium",

    "gpt-6-astra": "orlando-quinn",
    "gpt-6.0-astra": "orlando-quinn",
    "orlando-quinn": "orlando-quinn",

    # Anthropic / Claude
    "opus-5.5": "albuquerque-quinn",
    "opus-5-5": "albuquerque-quinn",
    "claude-opus-5.5": "albuquerque-quinn",
    "claude-opus-5-5": "albuquerque-quinn",
    "albuquerque-quinn": "albuquerque-quinn",

    "sonnet-4.6": "almond-croissant-low",
    "sonnet-4-6": "almond-croissant-low",
    "claude-sonnet-4.6": "almond-croissant-low",
    "claude-sonnet-4-6": "almond-croissant-low",
    "almond-croissant-low": "almond-croissant-low",

    "sonnet-5": "angel-cake-high",
    "claude-sonnet-5": "angel-cake-high",
    "angel-cake-high": "angel-cake-high",

    "sonnet-5.5": "achira-donut",
    "sonnet-5-5": "achira-donut",
    "claude-sonnet-5.5": "achira-donut",
    "claude-sonnet-5-5": "achira-donut",
    "achira-donut": "achira-donut",

    "opus-4.6": "avocado-froyo-medium",
    "opus-4-6": "avocado-froyo-medium",
    "claude-opus-4.6": "avocado-froyo-medium",
    "claude-opus-4-6": "avocado-froyo-medium",
    "avocado-froyo-medium": "avocado-froyo-medium",

    "opus-4.7": "apricot-sorbet-high",
    "opus-4-7": "apricot-sorbet-high",
    "claude-opus-4.7": "apricot-sorbet-high",
    "claude-opus-4-7": "apricot-sorbet-high",
    "apricot-sorbet-high": "apricot-sorbet-high",

    "opus-4.8": "ambrosia-tart-high",
    "opus-4-8": "ambrosia-tart-high",
    "claude-opus-4.8": "ambrosia-tart-high",
    "claude-opus-4-8": "ambrosia-tart-high",
    "ambrosia-tart-high": "ambrosia-tart-high",

    "opus-5": "agave-flan",
    "claude-opus-5": "agave-flan",
    "agave-flan": "agave-flan",

    "haiku-4.5": "anthropic-haiku-4.5",
    "haiku-4-5": "anthropic-haiku-4.5",
    "claude-haiku-4.5": "anthropic-haiku-4.5",
    "claude-haiku-4-5": "anthropic-haiku-4.5",
    "anthropic-haiku-4.5": "anthropic-haiku-4.5",

    "fable-5.1": "assam-chai",
    "fable-5-1": "assam-chai",
    "claude-fable-5.1": "assam-chai",
    "claude-fable-5-1": "assam-chai",
    "assam-chai": "assam-chai",

    "fable-5": "acai-budino-high",
    "claude-fable-5": "acai-budino-high",
    "acai-budino-high": "acai-budino-high",

    # Google Gemini
    "gemini-3.5-flash": "vertex-gemini-3.5-flash",
    "gemini-3-5-flash": "vertex-gemini-3.5-flash",
    "vertex-gemini-3.5-flash": "vertex-gemini-3.5-flash",

    "gemini-3.6-flash": "vertex-gemini-3.6-flash",
    "gemini-3-6-flash": "vertex-gemini-3.6-flash",
    "vertex-gemini-3.6-flash": "vertex-gemini-3.6-flash",

    "gemini-3.7-flash": "grapefruit-zeppole",
    "gemini-3-7-flash": "grapefruit-zeppole",
    "grapefruit-zeppole": "grapefruit-zeppole",

    "gemini-3.1-pro": "galette-medium-thinking",
    "gemini-3-1-pro": "galette-medium-thinking",
    "galette-medium-thinking": "galette-medium-thinking",

    "gemini-3-flash": "gingerbread",
    "gingerbread": "gingerbread",

    # DeepSeek
    "deepseek-v4-pro": "baseten-deepseek-v4-pro",
    "deepseek-v4": "baseten-deepseek-v4-pro",
    "baseten-deepseek-v4-pro": "baseten-deepseek-v4-pro",

    "deepseek-v4-flash": "baseten-deepseek-v4-flash",
    "baseten-deepseek-v4-flash": "baseten-deepseek-v4-flash",

    "deepseek-v4.1-flash": "baseten-deepseek-v4.1-flash",
    "deepseek-v4-1-flash": "baseten-deepseek-v4.1-flash",
    "baseten-deepseek-v4.1-flash": "baseten-deepseek-v4.1-flash",

    # Moonshot Kimi
    "kimi-k3": "fireworks-kimi-k3",
    "fireworks-kimi-k3": "fireworks-kimi-k3",

    # Zhipu GLM
    "glm-5.2": "baseten-glm-5.2",
    "glm-5-2": "baseten-glm-5.2",
    "baseten-glm-5.2": "baseten-glm-5.2",

    "glm-5.3": "baseten-glm-5.3",
    "glm-5-3": "baseten-glm-5.3",
    "baseten-glm-5.3": "baseten-glm-5.3",

    "glm-5.3-flash": "baseten-glm-5.3-flash",
    "glm-5-3-flash": "baseten-glm-5.3-flash",
    "baseten-glm-5.3-flash": "baseten-glm-5.3-flash",

    # xAI Grok
    "grok-4.6": "soursop-shortcake",
    "grok-4-6": "soursop-shortcake",
    "soursop-shortcake": "soursop-shortcake",

    "grok-4.5": "strawberry-whoopiepie",
    "grok-4-5": "strawberry-whoopiepie",
    "strawberry-whoopiepie": "strawberry-whoopiepie",

    "grok-4.3": "xigua-mochi-medium",
    "grok-4-3": "xigua-mochi-medium",
    "xigua-mochi-medium": "xigua-mochi-medium",

    "grok-build-0.1": "xinomavro-cake",
    "grok-build-0-1": "xinomavro-cake",
    "xinomavro-cake": "xinomavro-cake",
}


def normalize_cookie(raw: str) -> str:
    trimmed = raw.strip()
    if not trimmed:
        return ""
    return trimmed if "=" in trimmed else f"token_v2={trimmed}"


def resolve_codename(model: Optional[str]) -> str:
    if not model:
        return ""
    clean = model.lower().strip()
    for prefix in ("notion_web/", "notion-web/", "nw/"):
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
            break
    if clean in ("notion-ai", "default", "auto"):
        return ""

    if clean in NOTION_CODENAMES:
        return NOTION_CODENAMES[clean]

    # Try dot to hyphen normalization or vice-versa
    hyphen_variant = clean.replace(".", "-")
    if hyphen_variant in NOTION_CODENAMES:
        return NOTION_CODENAMES[hyphen_variant]

    dot_variant = clean.replace("-", ".")
    if dot_variant in NOTION_CODENAMES:
        return NOTION_CODENAMES[dot_variant]

    # Try removing claude- prefix
    if clean.startswith("claude-"):
        no_claude = clean[7:]
        if no_claude in NOTION_CODENAMES:
            return NOTION_CODENAMES[no_claude]
        if no_claude.replace(".", "-") in NOTION_CODENAMES:
            return NOTION_CODENAMES[no_claude.replace(".", "-")]

    return NOTION_CODENAMES.get(clean, clean)


def sanitize_notion_assistant_text(text: str) -> str:
    if not text:
        return ""
    clean = text.lstrip("\ufeff").strip()
    clean = re.sub(r"</?lang\b[^>]*\/?>", "", clean, flags=re.I)
    clean = re.sub(r"</lang>", "", clean, flags=re.I)
    if re.match(r"^<lang\b", clean, flags=re.I) and ">" not in clean:
        return ""
    return clean.strip()


def extract_notion_upstream_error(rec: Dict[str, Any]) -> Optional[str]:
    t = str(rec.get("type") or "").strip()
    if t == "error":
        msg = rec.get("message") or rec.get("subType") or "Internal Notion error"
        return f"Notion AI error: {msg}"
    if t == "premium-feature-unavailable":
        fa = rec.get("featureAvailability", {}) if isinstance(rec.get("featureAvailability"), dict) else {}
        lim = fa.get("limit", {}) if isinstance(fa.get("limit"), dict) else {}
        curr = lim.get("current")
        tot = lim.get("total")
        if curr is not None and tot is not None:
            return f"Notion AI error: Plan limit exceeded ({curr}/{tot} requests used). Upgrade to Notion Business/Enterprise required."
        return "Notion AI error: Premium feature unavailable on current Notion plan."

    # Check patch-start data.s
    if t == "patch-start" and isinstance(rec.get("data"), dict):
        for s_item in rec["data"].get("s", []):
            if isinstance(s_item, dict):
                st = s_item.get("type")
                if st == "error":
                    msg = s_item.get("message") or s_item.get("subType") or "Unknown error"
                    sub = s_item.get("subType")
                    return f"Notion AI error: {msg} ({sub})" if sub and sub not in msg else f"Notion AI error: {msg}"
                if st == "premium-feature-unavailable":
                    fa = s_item.get("featureAvailability", {}) if isinstance(s_item.get("featureAvailability"), dict) else {}
                    lim = fa.get("limit", {}) if isinstance(fa.get("limit"), dict) else {}
                    curr = lim.get("current")
                    tot = lim.get("total")
                    if curr is not None and tot is not None:
                        return f"Notion AI error: Plan limit exceeded ({curr}/{tot} requests used). Upgrade to Notion Business/Enterprise required."
                    return "Notion AI error: Premium feature unavailable on current Notion plan."

    # Check patch v ops
    if t == "patch" and isinstance(rec.get("v"), list):
        for op in rec["v"]:
            if isinstance(op, dict):
                v = op.get("v")
                if isinstance(v, dict):
                    vt = v.get("type")
                    if vt == "error":
                        return f"Notion AI error: {v.get('message') or v.get('subType') or 'Error'}"
                    if vt == "premium-feature-unavailable":
                        fa = v.get("featureAvailability", {}) if isinstance(v.get("featureAvailability"), dict) else {}
                        lim = fa.get("limit", {}) if isinstance(fa.get("limit"), dict) else {}
                        curr = lim.get("current")
                        tot = lim.get("total")
                        if curr is not None and tot is not None:
                            return f"Notion AI error: Plan limit exceeded ({curr}/{tot} requests used). Upgrade to Notion Business/Enterprise required."
                        return "Notion AI error: Premium feature unavailable on current Notion plan."
    return None


def extract_text_from_stream(raw: str, exclude_texts: Optional[Set[str]] = None) -> str:
    """
    Parses Notion NDJSON runInferenceTranscript stream lines into assistant text.
    Matches Omniroute's accumulator and priority logic, with error checking and prompt exclusion.
    """
    last_legacy = ""
    last_patch_final = ""
    last_incremental = ""
    last_record_map = ""

    for line in raw.split("\n"):
        line = line.strip()
        if not line or line == "[DONE]":
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
        try:
            rec = json.loads(line)
        except Exception:
            continue

        if not isinstance(rec, dict):
            continue

        # In-band error detection
        err = extract_notion_upstream_error(rec)
        if err:
            raise RuntimeError(err)

        t = rec.get("type", "")

        # 1. Direct markdown-chat or agent-inference
        if t == "markdown-chat" and isinstance(rec.get("value"), str) and rec.get("value"):
            last_patch_final = rec["value"]
        elif t == "agent-inference" and isinstance(rec.get("value"), list):
            parts = []
            for part in rec["value"]:
                if isinstance(part, dict) and part.get("type") == "text" and part.get("content"):
                    parts.append(part["content"])
            if parts:
                last_patch_final = "".join(parts)

        # 2. Patch stream
        elif t == "patch" and isinstance(rec.get("v"), list):
            for op in rec["v"]:
                if isinstance(op, dict):
                    v = op.get("v")
                    p = str(op.get("p", ""))
                    o = str(op.get("o", ""))
                    if isinstance(v, dict):
                        vt = v.get("type")
                        if vt == "text" and v.get("content"):
                            last_patch_final = v["content"]
                        elif vt == "markdown-chat" and v.get("value"):
                            last_patch_final = v["value"]
                    elif isinstance(v, str) and (o in ("x", "p")) and "/value" in p and v:
                        last_incremental += v

        # 3. RecordMap thread_message
        elif "recordMap" in rec or t == "record-map":
            rm = rec.get("recordMap") or rec
            tm = rm.get("thread_message") if isinstance(rm, dict) else None
            if isinstance(tm, dict):
                best_rm = ""
                for msg in tm.values():
                    val = msg.get("value", {}).get("value", {}).get("step", {})
                    step_type = val.get("type")
                    text = ""
                    if step_type == "markdown-chat" and isinstance(val.get("value"), str):
                        text = val["value"]
                    elif step_type == "agent-inference" and isinstance(val.get("value"), list):
                        parts = [
                            p.get("content", "")
                            for p in val["value"]
                            if isinstance(p, dict) and p.get("type") == "text"
                        ]
                        text = "".join(parts)
                    # Exclude any message that was part of the input prompt
                    if text and exclude_texts and text.strip() in exclude_texts:
                        continue
                    if text and len(text) >= len(best_rm):
                        best_rm = text
                if best_rm:
                    last_record_map = best_rm

        # 4. Legacy rich-text value
        elif isinstance(rec.get("value"), list):
            rich_parts = []
            for segment in rec["value"]:
                if isinstance(segment, list) and segment and isinstance(segment[0], str):
                    rich_parts.append(segment[0])
            if rich_parts:
                last_legacy = "".join(rich_parts)

    candidates = [
        sanitize_notion_assistant_text(c)
        for c in [last_record_map, last_patch_final, last_incremental, last_legacy]
    ]
    valid = [c for c in candidates if c and not (exclude_texts and c in exclude_texts)]
    if not valid:
        return ""
    # Sort by length descending, preferring record-map or longest sanitized content
    return sorted(valid, key=len, reverse=True)[0]


class NotionWebAdapter(BaseModuleAdapter):
    """
    Adapter for Notion AI Web internal inference endpoint.
    """

    def _get_cookie(self, ctx: ModuleExecutionContext) -> str:
        cookie = (
            ctx.credentials.get("token_v2")
            or ctx.credentials.get("cookie")
            or ctx.credentials.get("apiKey")
            or ""
        )
        return normalize_cookie(str(cookie).strip())

    def _build_headers(self, cookie: str, space_id: str = "", user_id: str = "") -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/x-ndjson",
            "User-Agent": USER_AGENT,
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/ai",
            "notion-client-version": NOTION_CLIENT_VERSION,
            "notion-audit-log-platform": "web",
            "Cookie": cookie,
            "sec-ch-ua": '"Chromium";v="149", "Not)A;Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if space_id:
            headers["x-notion-space-id"] = space_id
        if user_id:
            headers["x-notion-active-user-header"] = user_id
        return headers

    async def _resolve_workspace_and_user(
        self, client: httpx.AsyncClient, cookie: str, manual_space: Optional[str] = None
    ) -> Tuple[str, str]:
        user_id = ""
        m_user = re.search(r"(?:^|;\s*)(?:notion_user_id|user_id)=([^;]+)", cookie, re.I)
        if m_user:
            user_id = m_user.group(1).strip()

        space_id = ""
        if manual_space and manual_space.strip():
            space_id = manual_space.strip()
        else:
            m = re.search(r"(?:^|;\s*)space_id=([^;]+)", cookie, re.I)
            if m:
                space_id = m.group(1).strip()

        if not space_id or not user_id:
            try:
                resp = await client.post(NOTION_SPACES_URL, headers=self._build_headers(cookie), json={}, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict):
                        for u_key, v in data.items():
                            if not user_id and u_key and " " not in u_key:
                                user_id = u_key
                            if isinstance(v, dict) and "space" in v and isinstance(v["space"], dict):
                                keys = list(v["space"].keys())
                                if keys and not space_id:
                                    space_id = keys[0]
            except Exception as e:
                logger.warning(f"Failed to auto-resolve Notion workspace/user: {e}")

        return space_id, user_id

    async def _resolve_space_id(self, client: httpx.AsyncClient, cookie: str, manual_space: Optional[str] = None) -> str:
        space_id, _ = await self._resolve_workspace_and_user(client, cookie, manual_space)
        return space_id

    async def validate_credentials(
        self,
        ctx: ModuleExecutionContext,
    ) -> Tuple[bool, str, int]:
        cookie = self._get_cookie(ctx)
        if not cookie:
            return False, "Missing Notion token_v2 cookie", 0

        try:
            async with self.create_http_client(ctx) as client:
                manual_space = ctx.credentials.get("space_id")
                space_id, _ = await self._resolve_workspace_and_user(client, cookie, manual_space)
                if space_id:
                    models = await self.list_models(ctx)
                    return True, f"Notion session active (Workspace: {space_id})", len(models)
                return False, "Failed to resolve workspace from token_v2 (session may be expired)", 0
        except Exception as e:
            return False, f"Connection failed: {str(e)}", 0

    async def list_models(
        self,
        ctx: ModuleExecutionContext,
    ) -> List[DiscoveredModelData]:
        cookie = self._get_cookie(ctx)
        if cookie:
            try:
                async with self.create_http_client(ctx) as client:
                    manual_space = ctx.credentials.get("space_id")
                    space_id, user_id = await self._resolve_workspace_and_user(client, cookie, manual_space)
                    if space_id:
                        resp = await client.post(
                            NOTION_AVAILABLE_MODELS_URL,
                            headers=self._build_headers(cookie, space_id, user_id),
                            json={"spaceId": space_id},
                            timeout=10.0,
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            live_models = data.get("models", [])
                            if live_models:
                                result = [
                                    DiscoveredModelData(
                                        provider_model_id="notion-ai",
                                        display_name="Notion AI (Auto)",
                                        capabilities={"chat": True, "streaming": True, "vision": False, "tools": False, "reasoning": True},
                                        context_length=128000,
                                        max_output_tokens=4096,
                                    )
                                ]
                                for m in live_models:
                                    codename = m.get("model")
                                    if not codename:
                                        continue
                                    friendly_id = REVERSE_CODENAME_TO_ID.get(codename, codename)
                                    raw_title = m.get("modelMessage") or friendly_id.title()
                                    display_name = f"{raw_title} (Notion)"

                                    cfg = m.get("modelConfiguration") or {}
                                    has_reasoning = bool(cfg.get("supportedReasoningEfforts"))
                                    family = m.get("modelFamily", "")
                                    ctx_len = 200000 if family == "anthropic" else 128000

                                    result.append(
                                        DiscoveredModelData(
                                            provider_model_id=friendly_id,
                                            display_name=display_name,
                                            capabilities={"chat": True, "streaming": True, "vision": False, "tools": False, "reasoning": has_reasoning},
                                            context_length=ctx_len,
                                            max_output_tokens=8192 if has_reasoning else 4096,
                                        )
                                    )
                                return result
            except Exception as e:
                logger.warning(f"Failed to fetch live models from Notion getAvailableModels: {e}")

        manifest_path = Path(__file__).parent / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    defaults = data.get("default_models", [])
                    if defaults:
                        return [
                            DiscoveredModelData(
                                provider_model_id=m["id"],
                                display_name=m.get("name", m["id"]),
                                capabilities=m.get("capabilities", {"chat": True, "streaming": True, "vision": False, "tools": False, "reasoning": False}),
                                context_length=m.get("context_length", 128000),
                                max_output_tokens=m.get("max_output_tokens", 4096),
                            )
                            for m in defaults
                        ]
            except Exception as e:
                logger.warning(f"Failed to load models from manifest: {e}")

        return [
            DiscoveredModelData(
                provider_model_id=mid,
                display_name=f"{mid.title()} (Notion)",
                capabilities={"chat": True, "streaming": True, "vision": False, "tools": False, "reasoning": True},
                context_length=128000,
                max_output_tokens=4096,
            )
            for mid in ["notion-ai", "gpt-6.1-sol", "gpt-5.6-terra", "opus-5.5", "sonnet-4.6", "gemini-3.7-flash", "kimi-k3", "deepseek-v4-pro", "glm-5.3-flash", "grok-4.6"]
        ]

    def _build_transcript(
        self,
        messages: List[ChatMessage],
        model_codename: str,
        space_id: str,
        user_id: str = "",
    ) -> List[Dict[str, Any]]:
        now_iso = datetime.now(timezone.utc).isoformat()
        config_val = {
            "type": "workflow",
            "enableAgentAutomations": True,
            "enableAgentIntegrations": True,
            "enableCustomAgents": True,
            "enableScriptAgent": True,
            "enableAgentDiffs": True,
            "enableCsvAttachmentSupport": True,
            "enableComputer": True,
            "enableCreateAndRunThread": True,
            "enableAgentGenerateImage": True,
            "useWebSearch": True,
            "searchScopes": [{"type": "everything"}],
            "availableConnectors": [],
            "enableUserSessionContext": False,
            "isCustomAgent": False,
            "isCustomAgentBuilder": False,
            "isCustomAgentCreate": False,
            "isAgentResearchRequest": False,
            "useCustomAgentDraft": False,
            "modelFromUser": bool(model_codename),
            "databaseAgentConfigMode": False,
            "isOnboardingAgent": False,
            "isMobile": False,
        }
        if model_codename:
            config_val["model"] = model_codename

        context_val: Dict[str, Any] = {
            "timezone": "UTC",
            "surface": "ai_module",
            "currentDatetime": now_iso,
            "spaceId": space_id,
        }
        if user_id:
            context_val["userId"] = user_id

        transcript: List[Dict[str, Any]] = [
            {"id": str(uuid.uuid4()), "type": "config", "value": config_val},
            {"id": str(uuid.uuid4()), "type": "context", "value": context_val},
        ]

        # Ignore leading assistant greeting (e.g. from Playground UI initial state)
        first_user_idx = -1
        for idx, m in enumerate(messages):
            if (m.role or "").lower() == "user":
                first_user_idx = idx
                break

        effective_messages = messages[first_user_idx:] if first_user_idx != -1 else messages

        for m in effective_messages:
            text = m.content if isinstance(m.content, str) else json.dumps(m.content)
            if not text:
                continue
            role = (m.role or "").lower()
            if role in ("system", "developer"):
                existing = transcript[1]["value"].get("instructions", "")
                transcript[1]["value"]["instructions"] = f"{existing}\n{text}".strip() if existing else text
            elif role == "assistant":
                transcript.append({
                    "id": str(uuid.uuid4()),
                    "type": "agent-inference",
                    "value": [{"type": "text", "content": text}],
                })
            else:
                user_step: Dict[str, Any] = {
                    "id": str(uuid.uuid4()),
                    "type": "user",
                    "value": [[text]],
                    "createdAt": now_iso,
                }
                if user_id:
                    user_step["userId"] = user_id
                transcript.append(user_step)

        return transcript

    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> ChatCompletionResponse:
        cookie = self._get_cookie(ctx)
        if not cookie:
            raise RuntimeError("Missing Notion token_v2 cookie")

        model_name = request.model or ctx.model_id or "notion-ai"
        codename = resolve_codename(model_name)

        async with self.create_http_client(ctx) as client:
            manual_space = ctx.credentials.get("space_id")
            space_id, user_id = await self._resolve_workspace_and_user(client, cookie, manual_space)
            if not space_id:
                raise RuntimeError("Could not resolve Notion workspace space_id")

            # Collect known assistant texts from input messages to avoid echoing them from thread history
            known_assistant_texts = {
                m.content.strip() for m in request.messages
                if (m.role or "").lower() == "assistant" and isinstance(m.content, str) and m.content.strip()
            }

            thread_id = str(uuid.uuid4())
            transcript = self._build_transcript(request.messages, codename, space_id, user_id)

            def build_req_payload(create_thread: bool) -> Dict[str, Any]:
                return {
                    "traceId": str(uuid.uuid4()),
                    "spaceId": space_id,
                    "threadId": thread_id,
                    "createThread": create_thread,
                    "generateTitle": create_thread,
                    "asPatchResponse": True,
                    "patchResponseVersion": 2,
                    "isPartialTranscript": not create_thread,
                    "saveAllThreadOperations": True,
                    "setUnreadState": create_thread,
                    "createdSource": "ai_module",
                    "threadType": "workflow",
                    "supportsCustomAgentNudgeTranscriptStep": True,
                    "isUserInAnySalesAssistedSpace": False,
                    "isSpaceSalesAssisted": False,
                    "transcript": transcript,
                    "threadParentPointer": {"table": "space", "id": space_id, "spaceId": space_id},
                    "debugOverrides": {
                        "annotationInferences": {},
                        "cachedInferences": {},
                        "emitAgentSearchExtractedResults": True,
                        "emitInferences": False,
                    },
                }

            headers = self._build_headers(cookie, space_id, user_id)
            resp = await client.post(NOTION_URL, headers=headers, json=build_req_payload(True), timeout=ctx.timeout or 120.0)
            if resp.status_code != 200:
                raise RuntimeError(f"Notion AI error (HTTP {resp.status_code}): {resp.text[:300]}")

            try:
                final_text = extract_text_from_stream(resp.text, exclude_texts=known_assistant_texts)
            except RuntimeError as err:
                err_lower = str(err).lower()
                is_quota = "premium" in err_lower or "limit" in err_lower
                is_transient = ("temporarily" in err_lower or "unavailable" in err_lower or "timeout" in err_lower) and not is_quota
                # If temporarily-unavailable, retry once with createThread=False (matches Omniroute)
                if is_transient:
                    await asyncio.sleep(0.8)
                    retry_resp = await client.post(
                        NOTION_URL, headers=headers, json=build_req_payload(False), timeout=ctx.timeout or 120.0
                    )
                    if retry_resp.status_code == 200:
                        final_text = extract_text_from_stream(retry_resp.text, exclude_texts=known_assistant_texts)
                    else:
                        raise err
                else:
                    raise err

            if not final_text:
                raise RuntimeError("No text returned by Notion AI")

            return ChatCompletionResponse(
                id=f"chatcmpl-notion-{uuid.uuid4().hex[:12]}",
                object="chat.completion",
                created=int(time.time()),
                model=model_name,
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=ChatMessage(role="assistant", content=final_text),
                        finish_reason="stop",
                    )
                ],
                usage=UsageInfo(
                    prompt_tokens=len(str(request.messages)) // 4,
                    completion_tokens=len(final_text) // 4,
                    total_tokens=(len(str(request.messages)) + len(final_text)) // 4,
                ),
            )

    async def stream_chat(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> AsyncGenerator[str, None]:
        resp = await self.chat_completions(request, ctx)
        text = resp.choices[0].message.content or ""
        req_id = f"chatcmpl-notion-{uuid.uuid4().hex[:12]}"
        created_ts = int(time.time())

        # Yield role chunk
        role_chunk = {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": created_ts,
            "model": request.model or ctx.model_id,
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(role_chunk)}\n\n"

        # Yield text content
        content_chunk = {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": created_ts,
            "model": request.model or ctx.model_id,
            "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(content_chunk)}\n\n"

        # Yield stop
        stop_chunk = {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": created_ts,
            "model": request.model or ctx.model_id,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(stop_chunk)}\n\n"
        yield "data: [DONE]\n\n"
