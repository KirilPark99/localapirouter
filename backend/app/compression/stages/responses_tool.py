import json
import re
import time
from typing import Any, Dict, List
from app.schemas.chat import ChatMessage
from app.compression.base import BaseCompressionStage, StageConfigField, CompressionContext, StageExecutionResult
from app.compression.tokenizer import count_messages_tokens

class ResponsesToolStage(BaseCompressionStage):
    id = "responses_tool"
    name = "Responses Tool Output"
    description = "Компактизация структурированного вывода инструментов (JSON, патчи, diff hunks) без потери данных."
    icon = "Wrench"
    default_order = 12
    default_enabled = True
    is_builtin = True

    JSON_BLOCK_RE = re.compile(r'```(?:json)?\s*([{\[][\s\S]*?[}\]])\s*```')

    def get_config_schema(self) -> List[StageConfigField]:
        return [
            StageConfigField(
                key="compact_json",
                label="Уплотнять JSON в ответах тулов",
                type="boolean",
                default_value=True,
                description="Удалять незначащие отступы из форматированного JSON",
            ),
            StageConfigField(
                key="min_json_bytes",
                label="Мин. размер JSON (байт)",
                type="number",
                default_value=120,
                min_value=50,
                max_value=2000,
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

        compact_json = config.get("compact_json", True)
        min_bytes = int(config.get("min_json_bytes", 120))

        compressed_messages: List[ChatMessage] = []
        modified = False
        rules_applied = []

        for msg in messages:
            if not isinstance(msg.content, str):
                compressed_messages.append(msg)
                continue

            content = msg.content
            orig = content

            if compact_json:
                # 1. Direct JSON body
                trimmed = content.strip()
                if (trimmed.startswith("{") and trimmed.endswith("}")) or (trimmed.startswith("[") and trimmed.endswith("]")):
                    if len(trimmed) >= min_bytes:
                        try:
                            parsed = json.loads(trimmed)
                            compacted = json.dumps(parsed, separators=(',', ':'), ensure_ascii=False)
                            if len(compacted) < len(content):
                                content = compacted
                                modified = True
                                rules_applied.append("compact_root_json")
                        except Exception:
                            pass

                # 2. JSON fenced blocks
                def _compact_fenced_json(match: re.Match) -> str:
                    nonlocal modified
                    raw_json = match.group(1).strip()
                    if len(raw_json) >= min_bytes:
                        try:
                            parsed = json.loads(raw_json)
                            c = json.dumps(parsed, separators=(',', ':'), ensure_ascii=False)
                            if len(c) < len(raw_json):
                                modified = True
                                return f"```json\n{c}\n```"
                        except Exception:
                            pass
                    return match.group(0)

                content = self.JSON_BLOCK_RE.sub(_compact_fenced_json, content)

            if content != orig:
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
            compressed=modified and final_tokens < initial_tokens,
            tokens_before=initial_tokens,
            tokens_after=final_tokens,
            savings_percent=savings,
            duration_ms=duration,
            rules_applied=list(set(rules_applied)),
        )
