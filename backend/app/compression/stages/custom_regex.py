import re
import time
from typing import Any, Dict, List
from app.schemas.chat import ChatMessage
from app.compression.base import BaseCompressionStage, StageConfigField, CompressionContext, StageExecutionResult
from app.compression.preservation import PreservationGuards
from app.compression.tokenizer import count_messages_tokens

class CustomRegexStage(BaseCompressionStage):
    id = "custom_regex"
    name = "Custom Regex Filter"
    description = "Пользовательский этап сжатия на основе регулярных выражений и текстовых замен."
    icon = "Sliders"
    stage_type = "custom_regex"
    default_order = 50
    default_enabled = True
    is_builtin = False

    def get_config_schema(self) -> List[StageConfigField]:
        return [
            StageConfigField(
                key="rules",
                label="Правила замены (JSON список)",
                type="textarea",
                default_value='[{"pattern": "\\\\b(foo)\\\\b", "replacement": "bar", "case_sensitive": false}]',
                description="Список правил замены в формате JSON: pattern, replacement, case_sensitive",
            ),
            StageConfigField(
                key="guard_code_blocks",
                label="Защищать блоки кода от замен",
                type="boolean",
                default_value=True,
                description="Не применять пользовательские замены внутри кода (```...```)",
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

        guard_code = config.get("guard_code_blocks", True)
        raw_rules = config.get("rules", [])
        if isinstance(raw_rules, str):
            import json
            try:
                raw_rules = json.loads(raw_rules)
            except Exception:
                raw_rules = []

        compiled_rules = []
        for r in raw_rules:
            if isinstance(r, dict) and "pattern" in r:
                try:
                    flags = 0 if r.get("case_sensitive", False) else re.IGNORECASE
                    compiled_rules.append((re.compile(r["pattern"], flags), r.get("replacement", "")))
                except Exception:
                    pass

        if not compiled_rules:
            return StageExecutionResult(
                stage_id=self.id,
                stage_name=self.name,
                messages=messages,
                compressed=False,
                tokens_before=initial_tokens,
                tokens_after=initial_tokens,
            )

        compressed_messages: List[ChatMessage] = []
        replacements_made = 0

        for msg in messages:
            if not isinstance(msg.content, str):
                compressed_messages.append(msg)
                continue

            content = msg.content
            if guard_code:
                text_to_process, preserved = PreservationGuards.extract(content)
            else:
                text_to_process, preserved = content, []

            orig_proc = text_to_process
            for pat, repl in compiled_rules:
                text_to_process, count = pat.subn(repl, text_to_process)
                replacements_made += count

            if guard_code:
                restored = PreservationGuards.restore(text_to_process, preserved)
            else:
                restored = text_to_process

            if restored != content:
                compressed_messages.append(msg.model_copy(update={"content": restored}))
            else:
                compressed_messages.append(msg)

        final_tokens = count_messages_tokens(compressed_messages)
        savings = max(0.0, round(((initial_tokens - final_tokens) / max(1, initial_tokens)) * 100, 2))
        duration = round((time.perf_counter() - t0) * 1000, 2)

        return StageExecutionResult(
            stage_id=self.id,
            stage_name=self.name,
            messages=compressed_messages,
            compressed=replacements_made > 0 and final_tokens < initial_tokens,
            tokens_before=initial_tokens,
            tokens_after=final_tokens,
            savings_percent=savings,
            duration_ms=duration,
            rules_applied=[f"custom_rules_applied:{replacements_made}"] if replacements_made > 0 else [],
        )
