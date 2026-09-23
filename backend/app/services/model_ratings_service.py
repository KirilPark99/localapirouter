import os
import re
import json
import logging
import urllib.request
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "artificial_analysis_cache.json"

class ModelRatingsService:
    _initialized: bool = False
    _models: List[Dict[str, Any]] = []
    _by_openrouter: Dict[str, Dict[str, Any]] = {}
    _by_slug: Dict[str, Dict[str, Any]] = {}
    _by_norm: Dict[str, Dict[str, Any]] = {}
    _updated_at: Optional[str] = None

    @classmethod
    def _normalize(cls, text: Optional[str]) -> str:
        if not text:
            return ""
        t = str(text).lower().strip()
        t = t.replace("/", "-").replace(".", "-").replace("_", "-").replace(":", "-")
        # Remove date stamps and common noise tokens
        t = re.sub(r"-(202\d{5}|202\d-\d{2}-\d{2}|preview|latest|chat|it|instruct|exp|v\d+|default|free|turbo|batch|online)", "", t)
        t = re.sub(r"[^a-z0-9]", "", t)
        return t

    @classmethod
    def ensure_initialized(cls):
        if cls._initialized:
            return
        cls.load_from_cache()

    @classmethod
    def load_from_cache(cls):
        cls._by_openrouter.clear()
        cls._by_slug.clear()
        cls._by_norm.clear()
        cls._models.clear()

        if not CACHE_FILE.exists():
            logger.warning(f"Artificial Analysis cache file not found at {CACHE_FILE}")
            cls._initialized = True
            return

        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)

            cls._updated_at = payload.get("updated_at")
            cls._models = payload.get("models", [])

            for m in cls._models:
                intel = m.get("intelligence_index")
                if intel is None:
                    continue

                # Index by openrouter ID
                or_id = m.get("openrouter_id")
                if or_id:
                    or_id_lower = or_id.lower().strip()
                    cls._by_openrouter[or_id_lower] = m
                    if "/" in or_id_lower:
                        sub = or_id_lower.split("/", 1)[1]
                        cls._by_openrouter[sub] = m

                # Index by slug
                slug = m.get("slug")
                if slug:
                    slug_lower = slug.lower().strip()
                    cls._by_slug[slug_lower] = m
                    cls._by_norm[cls._normalize(slug)] = m

                # Index by names
                name = m.get("name")
                if name:
                    cls._by_norm[cls._normalize(name)] = m
                short_name = m.get("short_name")
                if short_name:
                    cls._by_norm[cls._normalize(short_name)] = m

            cls._initialized = True
            logger.info(f"Loaded {len(cls._models)} Artificial Analysis benchmark models into memory.")
        except Exception as e:
            logger.error(f"Failed to load Artificial Analysis cache: {e}")
            cls._initialized = True

    @classmethod
    def find_rating(
        cls,
        provider_model_id: str,
        canonical_slug: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        cls.ensure_initialized()

        candidates: List[str] = []
        if canonical_slug:
            candidates.append(canonical_slug.lower().strip())
            if "/" in canonical_slug:
                candidates.append(canonical_slug.lower().strip().split("/", 1)[1])
        if provider_model_id:
            candidates.append(provider_model_id.lower().strip())
            if "/" in provider_model_id:
                candidates.append(provider_model_id.lower().strip().split("/", 1)[1])

        # 1. Exact match against OpenRouter ID index
        for cand in candidates:
            if cand in cls._by_openrouter:
                return cls._format_rating(cls._by_openrouter[cand])

        # 2. Exact match against slug index (with dots changed to dashes)
        for cand in candidates:
            slug_cand = cand.replace(".", "-").replace("_", "-")
            if slug_cand in cls._by_slug:
                return cls._format_rating(cls._by_slug[slug_cand])

        # 3. Normalized token matching on provider_model_id
        norm_p = cls._normalize(provider_model_id)
        if norm_p and norm_p in cls._by_norm:
            return cls._format_rating(cls._by_norm[norm_p])

        # 4. Normalized token matching on canonical_slug
        if canonical_slug:
            norm_c = cls._normalize(canonical_slug)
            if norm_c and norm_c in cls._by_norm:
                return cls._format_rating(cls._by_norm[norm_c])

        # 5. Normalized token matching on display_name
        if display_name:
            norm_d = cls._normalize(display_name)
            if norm_d and norm_d in cls._by_norm:
                return cls._format_rating(cls._by_norm[norm_d])

        return None

    @classmethod
    def _format_rating(cls, raw: Dict[str, Any]) -> Dict[str, Any]:
        slug = raw.get("slug") or ""
        return {
            "intelligence_index": raw.get("intelligence_index"),
            "coding_index": raw.get("coding_index"),
            "agentic_index": raw.get("agentic_index"),
            "speed_tokens_per_sec": raw.get("speed_tokens_per_sec"),
            "is_reasoning": bool(raw.get("is_reasoning", False)),
            "eval_provider": "Artificial Analysis",
            "source_url": f"https://artificialanalysis.ai/models/{slug}" if slug else "https://artificialanalysis.ai",
            "model_creator": raw.get("creator"),
            "aa_name": raw.get("name"),
            "aa_slug": slug,
        }

    @classmethod
    def sync_from_web(cls) -> Dict[str, Any]:
        """Scrape latest benchmark index from artificialanalysis.ai and update cache."""
        url = "https://artificialanalysis.ai/leaderboards/models"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            raise RuntimeError(f"Could not connect to artificialanalysis.ai: {e}")

        scripts = re.findall(r"<script[^>]*>(.*?)</script>", html)
        target_script = None
        for scr in scripts:
            if "intelligenceIndex" in scr and "modelCreatorName" in scr:
                target_script = scr
                break

        if not target_script:
            raise RuntimeError("Could not find benchmark payload in artificialanalysis.ai page")

        prefix = 'self.__next_f.push([1,"'
        idx = target_script.find(prefix)
        if idx == -1:
            raise RuntimeError("Could not locate Next.js payload stream in script")

        raw = target_script[idx + len(prefix):]
        for ending in ['"]);', '"])', '"]']:
            if raw.endswith(ending):
                raw = raw[:-len(ending)]
                break

        decoded = json.loads('"' + raw + '"')
        m_idx = decoded.find('"models":[')
        if m_idx == -1:
            raise RuntimeError("Could not locate models array in decoded Next.js stream")

        start = m_idx + 9
        raw_models, _ = json.JSONDecoder().raw_decode(decoded[start:])

        clean_catalog = []
        for m in raw_models:
            intel = m.get("intelligenceIndex")
            clean_catalog.append({
                "id": m.get("id"),
                "name": m.get("name"),
                "short_name": m.get("shortName"),
                "slug": m.get("slug"),
                "creator": m.get("modelCreatorName"),
                "creator_slug": m.get("modelCreatorSlug"),
                "openrouter_id": m.get("openrouterApiId"),
                "intelligence_index": round(intel, 1) if intel is not None else None,
                "coding_index": round(m["codingIndex"], 1) if m.get("codingIndex") is not None else None,
                "agentic_index": round(m["agenticIndex"], 1) if m.get("agenticIndex") is not None else None,
                "speed_tokens_per_sec": round(m["medianOutputTokensPerSecond"], 1) if m.get("medianOutputTokensPerSecond") is not None else None,
                "context_tokens": m.get("contextWindowTokens"),
                "is_reasoning": m.get("isReasoning", False),
                "release_date": m.get("releaseDate"),
            })

        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "updated_at": "2026-09-04",
                "source": "https://artificialanalysis.ai",
                "models": clean_catalog,
            }, f, indent=2, ensure_ascii=False)

        cls._initialized = False
        cls.ensure_initialized()

        return {
            "success": True,
            "models_count": len(clean_catalog),
            "updated_at": cls._updated_at,
            "source": "https://artificialanalysis.ai",
        }
