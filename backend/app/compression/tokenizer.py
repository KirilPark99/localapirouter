import re
from typing import List, Union
from app.schemas.chat import ChatMessage

# Try importing tiktoken if available
_TIKTOKEN_ENCODING = None
try:
    import tiktoken
    try:
        _TIKTOKEN_ENCODING = tiktoken.get_encoding("cl100k_base")
    except Exception:
        pass
except ImportError:
    pass

def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a text.
    Uses tiktoken if installed; otherwise uses a robust multilingual heuristic
    that properly weights whitespace, punctuation, Latin and Cyrillic/CJK characters.
    """
    if not text:
        return 0

    if _TIKTOKEN_ENCODING is not None:
        try:
            return len(_TIKTOKEN_ENCODING.encode(text, disallowed_special=()))
        except Exception:
            pass

    # High-accuracy heuristic:
    # 1 token is approximately:
    # - ~4 characters of English text
    # - ~1.8-2 characters of Cyrillic text
    # - ~1-1.5 characters of CJK text
    # - Numbers and punctuation often break into individual or short tokens
    total = 0
    words_and_spaces = re.findall(r'\w+|[^\w\s]|\s+', text)
    for token in words_and_spaces:
        if token.isspace():
            total += max(1, len(token) // 4)
        elif all(ord(c) < 128 for c in token):
            # ASCII / Latin
            total += max(1, (len(token) + 3) // 4)
        elif any('\u0400' <= c <= '\u04FF' for c in token):
            # Cyrillic
            total += max(1, (len(token) + 1) // 2)
        else:
            # CJK / other scripts
            total += max(1, len(token))

    return max(1, total)

def count_messages_tokens(messages: List[Union[ChatMessage, dict]]) -> int:
    """
    Estimate total tokens across a list of ChatMessage or message dicts,
    including formatting overhead (~3 tokens per message role/delimiter).
    """
    if not messages:
        return 0

    total = 3  # conversation priming
    for m in messages:
        total += 3  # per message overhead
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else "")
        content = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else "")

        if role:
            total += estimate_tokens(str(role))
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    total += estimate_tokens(str(part["text"]))
                elif isinstance(part, str):
                    total += estimate_tokens(part)

    return total
