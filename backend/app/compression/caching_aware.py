"""Cache-aware coordination for Token Compression.
Ensures token compression doesn't destroy provider KV-caches (Prompt Caching)
for providers like Anthropic, OpenAI, DeepSeek, Google Gemini, Qwen, etc.
"""
from typing import Dict, Optional, Set

CACHING_PROVIDERS: Set[str] = {
    "anthropic",
    "claude",
    "openai",
    "azure",
    "deepseek",
    "google",
    "gemini",
    "alibaba",
    "qwen",
    "dashscope",
    "xiaomi",
    "mimo",
    "kimi",
    "moonshot",
}

CACHING_MODEL_PREFIXES = (
    "claude",
    "gpt-4o",
    "gpt-4.5",
    "o1",
    "o3",
    "deepseek",
    "gemini",
    "qwen",
    "moonshot",
    "kimi",
)


def is_prompt_caching_supported(model_id: str, provider_name: Optional[str] = None) -> bool:
    """
    Determines if the given model or provider supports upstream KV prompt caching.
    """
    if provider_name and provider_name.strip().lower() in CACHING_PROVIDERS:
        return True

    mid = model_id.strip().lower() if model_id else ""
    if "/" in mid:
        prov, mname = mid.split("/", 1)
        if prov in CACHING_PROVIDERS:
            return True
        mid = mname

    for prefix in CACHING_MODEL_PREFIXES:
        if mid.startswith(prefix) or f"/{prefix}" in mid or f"-{prefix}" in mid:
            return True

    return False


def should_preserve_system_prompt(
    mode: str,
    model_id: str,
    request_headers: Optional[Dict[str, str]] = None,
    provider_name: Optional[str] = None,
) -> bool:
    """
    Decides whether the system prompt should be preserved untouched during compression.

    Modes:
      - 'always': Always preserve system prompt (never compress system message).
      - 'never': Always allow compression of system prompt.
      - 'when_caching': Preserve system prompt if the upstream model/provider supports
        prompt caching or if explicit cache_control is requested.
    """
    normalized_mode = (mode or "when_caching").lower().strip()
    if normalized_mode == "always":
        return True
    if normalized_mode == "never":
        return False

    headers = request_headers or {}
    for k, v in headers.items():
        if "cache-control" in k.lower() and "no-cache" not in str(v).lower():
            return True

    if not provider_name and (not model_id or model_id.lower().startswith("route/")):
        return True  # Unknown resolved target must not destroy a potential cache prefix.
    return is_prompt_caching_supported(model_id, provider_name)
