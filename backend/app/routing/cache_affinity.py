"""Prompt Cache Affinity & Cache-Optimized Strategy.
Implements Rendezvous Hashing (HRW) and prefix analysis to route requests with
identical context/history to the same candidate/credential, maximizing upstream
KV-cache reuse (Anthropic Prompt Caching, OpenAI Automatic Prefix Caching, DeepSeek Context Caching).
"""
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple, Union
from app.schemas.chat import ChatMessage, ChatCompletionRequest
from app.models.entities import RoutingCandidate


class PrefixAnalyzer:
    """Analyzes message prefixes to identify stable, reusable prompt segments."""

    @staticmethod
    def normalize_content(content: Union[str, List[Any], Dict[str, Any], None]) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content.strip()
        try:
            return json.dumps(content, ensure_ascii=False, sort_keys=True)
        except Exception:
            return str(content)

    @classmethod
    def analyze_prefix(cls, messages: List[ChatMessage]) -> Dict[str, Any]:
        if not messages:
            return {
                "prefix_end_idx": -1,
                "prefix_hash": "",
                "prefix_tokens": 0,
                "confidence": 0.0,
            }

        prefix_end_idx = -1
        confidence = 0.5

        def _extract_msg(m: Any) -> Tuple[str, str]:
            if isinstance(m, dict):
                r = m.get("role") or "user"
                c = m.get("content") or ""
            else:
                r = getattr(m, "role", "user") or "user"
                c = getattr(m, "content", "") or ""
            return str(r).lower(), str(c)

        for i, msg in enumerate(messages):
            role, _ = _extract_msg(msg)
            if role == "system":
                prefix_end_idx = i
                confidence = 0.9
            elif role == "tool":
                prefix_end_idx = i
                confidence = 0.8
            elif role == "assistant" and i == 1:
                # Initial system + assistant greeting
                prefix_end_idx = i
                confidence = 0.7
            else:
                # Stop at subsequent user turns
                if i > 0 and prefix_end_idx >= 0:
                    break

        # If no explicit system message, but at least 2 messages exist, take first message as prefix
        if prefix_end_idx == -1 and len(messages) > 1:
            prefix_end_idx = 0
            confidence = 0.6

        if prefix_end_idx == -1:
            return {
                "prefix_end_idx": -1,
                "prefix_hash": "",
                "prefix_tokens": 0,
                "confidence": 0.0,
            }

        prefix_messages = messages[: prefix_end_idx + 1]
        prefix_parts = [
            f"{_extract_msg(m)[0]}:{cls.normalize_content(_extract_msg(m)[1])}"
            for m in prefix_messages
        ]
        prefix_text = "\n".join(prefix_parts)
        prefix_hash = hashlib.sha256(prefix_text.encode("utf-8")).hexdigest()
        prefix_tokens = max(1, len(prefix_text) // 4)

        return {
            "prefix_end_idx": prefix_end_idx,
            "prefix_hash": prefix_hash,
            "prefix_tokens": prefix_tokens,
            "confidence": confidence,
        }

    @classmethod
    def generate_prompt_cache_key(cls, messages: List[ChatMessage]) -> str:
        analysis = cls.analyze_prefix(messages)
        if analysis["prefix_hash"]:
            return f"myai-{analysis['prefix_hash'][:32]}"
        return ""


class RendezvousHasher:
    """Highest Random Weight (HRW) rendezvous hashing for deterministic cache affinity."""

    @staticmethod
    def target_identity(candidate: Union[RoutingCandidate, Any]) -> str:
        if isinstance(candidate, RoutingCandidate):
            return f"cand_{candidate.id}_model_{candidate.model_id}_cred_{candidate.credential_id or candidate.credential_group or 'def'}"
        if isinstance(candidate, tuple) and len(candidate) >= 2:
            # (cred, model_obj) tuple from direct route
            cred, model_obj = candidate[0], candidate[1]
            return f"cred_{getattr(cred, 'id', '0')}_m_{getattr(model_obj, 'provider_model_id', 'def')}"
        return str(getattr(candidate, "id", id(candidate)))

    @classmethod
    def score(cls, key: str, identity: str) -> float:
        """Computes deterministic normalized score in [0.0, 1.0]."""
        payload = f"{key}\0{identity}".encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        # Use first 16 hex chars (64-bit int)
        val = int(digest[:16], 16)
        max_val = 0xFFFFFFFFFFFFFFFF
        return val / max_val

    @classmethod
    def select_node(cls, key: str, nodes: List[str]) -> str:
        """Selects the node with highest rendezvous score for key."""
        if not nodes:
            return ""
        return max(nodes, key=lambda n: (cls.score(key, n), n))


def resolve_prompt_cache_key(request: Any) -> Optional[str]:
    """Resolves explicit client cache key or generates one from messages prefix."""
    if isinstance(request, list):
        return PrefixAnalyzer.generate_prompt_cache_key(request)

    if isinstance(request, dict):
        explicit = request.get("prompt_cache_key")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()
        msgs = request.get("messages")
        if msgs:
            return PrefixAnalyzer.generate_prompt_cache_key(msgs)
        return None

    # Check explicit key in request extra fields
    explicit = getattr(request, "prompt_cache_key", None)
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()

    # Generate from messages
    messages = getattr(request, "messages", None)
    if messages:
        key = PrefixAnalyzer.generate_prompt_cache_key(messages)
        if key:
            return key
    return None


def apply_prompt_cache_affinity(
    candidates: List[Any],
    request: ChatCompletionRequest,
    scope: str = "global",
) -> Tuple[List[Any], Dict[str, Any]]:
    """
    Reorders candidates using rendezvous hashing based on prompt cache key.
    If no key can be resolved or only 1 candidate exists, returns candidates untouched.
    """
    if len(candidates) <= 1:
        return candidates, {"applied": False, "reason": "single_candidate"}

    cache_key = resolve_prompt_cache_key(request)
    if not cache_key:
        return candidates, {"applied": False, "reason": "no_cache_key"}

    scored_entries = []
    for idx, cand in enumerate(candidates):
        ident = RendezvousHasher.target_identity(cand)
        score = RendezvousHasher.score(cache_key, ident)
        scored_entries.append((cand, score, ident, idx))

    # Sort descending by score; ties broken by identity
    scored_entries.sort(key=lambda x: (x[1], x[2]), reverse=True)
    reordered = [entry[0] for entry in scored_entries]
    winner_ident = scored_entries[0][2]
    fingerprint = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:12]

    changed = [c for c in reordered] != candidates

    return reordered, {
        "applied": True,
        "changed": changed,
        "key": cache_key,
        "fingerprint": fingerprint,
        "winner_target": winner_ident,
    }
