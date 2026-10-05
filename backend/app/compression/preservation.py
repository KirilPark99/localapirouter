import re
import uuid
from typing import List, Tuple, Dict, Any

class PreservedBlock:
    def __init__(self, placeholder: str, content: str, kind: str):
        self.placeholder = placeholder
        self.content = content
        self.kind = kind

class PreservationGuards:
    """
    Guards structured content (code blocks, inline code, math formulas, URLs)
    from being corrupted by prose or lossy compression stages.
    Replaces protected constructs with unalterable sentinel placeholders,
    allowing stages to operate on the surrounding text, and restores them verbatim.
    """

    FENCED_CODE_RE = re.compile(r'(```[\s\S]*?```)', re.MULTILINE)
    INLINE_CODE_RE = re.compile(r'(`[^`\n]+`)')
    MATH_BLOCK_RE = re.compile(r'(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\])', re.MULTILINE)
    INLINE_MATH_RE = re.compile(r'(?<!\$)\$(?!\s)([^\n\$]+?)(?<!\s)\$(?!\$)')
    QUOTED_RE = re.compile(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'")
    URL_RE = re.compile(r'(https?://[^\s<>"\'\)]+)')

    @classmethod
    def extract(cls, text: str) -> Tuple[str, List[PreservedBlock]]:
        if not text:
            return text, []

        blocks: List[PreservedBlock] = []
        seed = uuid.uuid4().hex[:8]
        counter = 0

        def _replace_fenced(match: re.Match) -> str:
            nonlocal counter
            ph = f"\u0000__PRESERVE_{seed}_{counter}__\u0000"
            blocks.append(PreservedBlock(ph, match.group(0), "fenced_code"))
            counter += 1
            return ph

        def _replace_math(match: re.Match) -> str:
            nonlocal counter
            ph = f"\u0000__PRESERVE_{seed}_{counter}__\u0000"
            blocks.append(PreservedBlock(ph, match.group(0), "math"))
            counter += 1
            return ph

        def _replace_inline_code(match: re.Match) -> str:
            nonlocal counter
            ph = f"\u0000__PRESERVE_{seed}_{counter}__\u0000"
            blocks.append(PreservedBlock(ph, match.group(0), "inline_code"))
            counter += 1
            return ph

        def _replace_url(match: re.Match) -> str:
            nonlocal counter
            ph = f"\u0000__PRESERVE_{seed}_{counter}__\u0000"
            blocks.append(PreservedBlock(ph, match.group(0), "url"))
            counter += 1
            return ph

        # 1. Fenced code first (largest blocks)
        res = cls.FENCED_CODE_RE.sub(_replace_fenced, text)
        # 2. Math blocks
        res = cls.MATH_BLOCK_RE.sub(_replace_math, res)
        # 3. Inline code
        res = cls.INLINE_CODE_RE.sub(_replace_inline_code, res)
        res = cls.INLINE_MATH_RE.sub(_replace_math, res)
        res = cls.QUOTED_RE.sub(_replace_inline_code, res)
        # 4. URLs
        res = cls.URL_RE.sub(_replace_url, res)

        return res, blocks

    @classmethod
    def transform_unprotected(cls, text, transform):
        masked, blocks = cls.extract(text)
        placeholders = {b.placeholder for b in blocks}
        parts = re.split('(' + '|'.join(re.escape(p) for p in placeholders) + ')', masked) if placeholders else [masked]
        return cls.restore(''.join(part if part in placeholders else transform(part) for part in parts), blocks)

    @classmethod
    def restore(cls, text: str, blocks: List[PreservedBlock]) -> str:
        if not blocks:
            return text
        if any(text.count(b.placeholder) != 1 for b in blocks):
            raise ValueError("Protected content was removed or duplicated")

        res = text
        for b in reversed(blocks):
            res = res.replace(b.placeholder, b.content)
        return res
