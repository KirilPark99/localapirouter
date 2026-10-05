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
                description="Protection of code, math, URLs and quoted literals is mandatory; this legacy setting is retained for compatibility",
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

        import asyncio
        from app.core.safe_regex import subn
        from app.compression.validation import validate_rules
        raw_rules = await asyncio.to_thread(validate_rules, config.get("rules", []))
        compressed_messages = []
        replacements_made = 0
        for msg in messages:
            if msg.role in {"system", "developer", "user", "tool", "function"} or not isinstance(msg.content, str):
                compressed_messages.append(msg)
                continue
            masked, blocks = PreservationGuards.extract(msg.content)
            separators = {b.placeholder for b in blocks}
            parts = re.split('(' + '|'.join(re.escape(p) for p in separators) + ')', masked) if separators else [masked]
            for i, part in enumerate(parts):
                if part in separators:
                    continue
                for rule in raw_rules:
                    part, count = await asyncio.to_thread(subn, rule['pattern'], rule.get('replacement', ''), part,
                                                         flags=0 if rule.get('case_sensitive', False) else re.IGNORECASE)
                    replacements_made += count
                parts[i] = part
            restored = PreservationGuards.restore(''.join(parts), blocks)
            compressed_messages.append(msg.model_copy(update={"content": restored}))

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
            warning="Protected spans are mandatory; guard_code_blocks=False ignored" if config.get("guard_code_blocks") is False else None,
            rules_applied=[f"custom_rules_applied:{replacements_made}"] if replacements_made > 0 else [],
        )
