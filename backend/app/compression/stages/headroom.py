import csv
import io
import json
import re
import time
from typing import Any, Dict, List
from app.schemas.chat import ChatMessage
from app.compression.base import BaseCompressionStage, StageConfigField, CompressionContext, StageExecutionResult
from app.compression.tokenizer import count_messages_tokens

class HeadroomStage(BaseCompressionStage):
    id = "headroom"
    name = "Headroom (SmartCrusher Tabular)"
    description = "Табличное сжатие однородных JSON-массивов без потерь (устраняет дублирование ключей объектов)."
    icon = "Table"
    default_order = 15
    default_enabled = True
    is_builtin = True

    JSON_ARRAY_RE = re.compile(r'```(?:json)?\s*(\[\s*\{[\s\S]*?\}\s*\])\s*```')

    def get_config_schema(self) -> List[StageConfigField]:
        return [
            StageConfigField(
                key="min_rows",
                label="Мин. строк в массиве",
                type="number",
                default_value=6,
                min_value=3,
                max_value=100,
                description="Минимальное количество однородных объектов для упаковки в таблицу",
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

        min_rows = int(config.get("min_rows", 6))
        compressed_messages: List[ChatMessage] = []
        modified = False
        tables_crushed = 0

        for msg in messages:
            if not isinstance(msg.content, str):
                compressed_messages.append(msg)
                continue

            content = msg.content
            orig = content

            # 1. Direct array content
            trimmed = content.strip()
            if trimmed.startswith("[") and trimmed.endswith("]"):
                crushed = self._try_crush_array(trimmed, min_rows)
                if crushed and len(crushed) < len(content):
                    content = crushed
                    modified = True
                    tables_crushed += 1

            # 2. Fenced array blocks
            def _crush_match(match: re.Match) -> str:
                nonlocal modified, tables_crushed
                raw = match.group(1).strip()
                crushed = self._try_crush_array(raw, min_rows)
                if crushed and len(crushed) < len(match.group(0)):
                    modified = True
                    tables_crushed += 1
                    return crushed
                return match.group(0)

            content = self.JSON_ARRAY_RE.sub(_crush_match, content)

            if content != orig:
                compressed_messages.append(ChatMessage(role=msg.role, content=content, name=msg.name))
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
            rules_applied=[f"crushed_tables:{tables_crushed}"] if tables_crushed > 0 else [],
        )

    def _try_crush_array(self, json_str: str, min_rows: int) -> str | None:
        try:
            arr = json.loads(json_str)
            if not isinstance(arr, list) or len(arr) < min_rows:
                return None

            # Check homogeneity: all items must be dicts with primitive values
            first = arr[0]
            if not isinstance(first, dict) or not first:
                return None

            keys = list(first.keys())
            for item in arr:
                if not isinstance(item, dict) or list(item.keys()) != keys:
                    return None
                # Check for flat scalar values
                for v in item.values():
                    if isinstance(v, (dict, list)):
                        return None

            # Format as compact tabular block
            output = io.StringIO()
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(keys)
            for item in arr:
                writer.writerow([item.get(k, "") for k in keys])

            csv_text = output.getvalue().strip()
            return f"```omni-tabular [{len(arr)} rows]\n{csv_text}\n```"
        except Exception:
            return None
