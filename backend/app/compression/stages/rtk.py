import re
import time
from typing import Any, Dict, List
from app.schemas.chat import ChatMessage
from app.compression.base import BaseCompressionStage, StageConfigField, CompressionContext, StageExecutionResult
from app.compression.tokenizer import count_messages_tokens

class RtkStage(BaseCompressionStage):
    id = "rtk"
    name = "RTK (Terminal & Tool Output Filter)"
    description = "Очистка терминального вывода от ANSI-кодов, прогресс-баров и умная обрезка логов без потери ошибок."
    icon = "Terminal"
    default_order = 10
    default_enabled = True
    is_builtin = True

    ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    SPINNER_PROGRESS_RE = re.compile(r'(\r[^\n\r]*[\b\-/\\|][^\n\r]*)')
    ERROR_SIGNAL_RE = re.compile(r'(error|failure|failed|fatal|exception|traceback|panic|syntaxerror|typeerror)', re.IGNORECASE)

    def get_config_schema(self) -> List[StageConfigField]:
        return [
            StageConfigField(
                key="strip_ansi",
                label="Удалять ANSI-коды и цвета",
                type="boolean",
                default_value=True,
                description="Очищать цветные теги и escape-коды терминала",
            ),
            StageConfigField(
                key="dedup_repeated_lines",
                label="Схлопывать повторяющиеся строки",
                type="boolean",
                default_value=True,
                description="Заменять 3+ одинаковых строки подряд на [... repeated N times ...]",
            ),
            StageConfigField(
                key="smart_truncate_threshold",
                label="Порог умной обрезки (строк)",
                type="number",
                default_value=50,
                min_value=15,
                max_value=500,
                description="Если вывод команды превышает N строк, оставлять начало, конец и все строки с ошибками",
            ),
            StageConfigField(
                key="head_lines",
                label="Строк в начале (Head)",
                type="number",
                default_value=12,
                min_value=3,
                max_value=100,
            ),
            StageConfigField(
                key="tail_lines",
                label="Строк в конце (Tail)",
                type="number",
                default_value=15,
                min_value=3,
                max_value=100,
            ),
        ]

    async def compress(
        self,
        messages: List[ChatMessage],
        config: Dict[str, Any],
        context: CompressionContext,
    ) -> StageExecutionResult:
        t0 = time.perf_counter()
        initial_tokens = count_messages_tokens(messages)

        strip_ansi = config.get("strip_ansi", True)
        dedup_lines = config.get("dedup_repeated_lines", True)
        threshold = int(config.get("smart_truncate_threshold", 50))
        head_n = int(config.get("head_lines", 12))
        tail_n = int(config.get("tail_lines", 15))

        compressed_messages: List[ChatMessage] = []
        rules_applied = []
        any_modified = False

        for msg in messages:
            if not isinstance(msg.content, str):
                compressed_messages.append(msg)
                continue

            content = msg.content
            orig = content

            # 1. Strip ANSI
            if strip_ansi and "\x1b" in content:
                content = self.ANSI_ESCAPE_RE.sub('', content)
                content = self.SPINNER_PROGRESS_RE.sub('', content)
                rules_applied.append("strip_ansi")

            # 2. Dedup repeated lines
            if dedup_lines:
                content = self._dedup_lines(content)

            # 3. Smart truncate on large tool/command outputs
            lines = content.splitlines()
            if len(lines) > threshold and (msg.role == "tool" or "```" in content or any(sig in content.lower() for sig in ["git ", "npm ", "pytest", "build", "stdout", "stderr"])):
                content = self._smart_truncate(lines, head_n, tail_n)
                rules_applied.append("smart_truncate")

            if content != orig:
                any_modified = True
                compressed_messages.append(msg.model_copy(update={"content": content}))
            else:
                compressed_messages.append(msg)

        final_tokens = count_messages_tokens(compressed_messages)
        savings = max(0.0, round(((initial_tokens - final_tokens) / max(1, initial_tokens)) * 100, 2))
        duration = round((time.perf_counter() - t0) * 1000, 2)

        return StageExecutionResult(
            stage_id=self.id,
            stage_name=self.name,
            messages=compressed_messages,
            compressed=any_modified and final_tokens < initial_tokens,
            tokens_before=initial_tokens,
            tokens_after=final_tokens,
            savings_percent=savings,
            duration_ms=duration,
            rules_applied=list(set(rules_applied)),
        )

    def _dedup_lines(self, text: str) -> str:
        lines = text.splitlines()
        if len(lines) < 3:
            return text

        result = []
        i = 0
        n = len(lines)
        while i < n:
            current = lines[i]
            # Count consecutive duplicates
            j = i + 1
            while j < n and lines[j].strip() == current.strip() and len(current.strip()) > 3:
                j += 1

            count = j - i
            if count >= 3:
                result.append(current)
                result.append(f"[... repeated {count - 1} times ...]")
                i = j
            else:
                result.append(current)
                i += 1

        return "\n".join(result)

    def _smart_truncate(self, lines: List[str], head_n: int, tail_n: int) -> str:
        if len(lines) <= (head_n + tail_n):
            return "\n".join(lines)

        head = lines[:head_n]
        middle = lines[head_n:-tail_n]
        tail = lines[-tail_n:]

        # Search middle for error / critical lines
        preserved_middle = []
        for line in middle:
            if self.ERROR_SIGNAL_RE.search(line):
                preserved_middle.append(line)

        truncated_count = len(middle) - len(preserved_middle)
        res = head
        if preserved_middle:
            res.append(f"[... truncated {truncated_count} non-error lines, preserving {len(preserved_middle)} error lines ...]")
            res.extend(preserved_middle)
        else:
            res.append(f"[... truncated {truncated_count} intermediate lines ...]")
        res.extend(tail)

        return "\n".join(res)
