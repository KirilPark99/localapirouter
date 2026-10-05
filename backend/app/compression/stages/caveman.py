import re
import time
from typing import Any, Dict, List, Tuple
from app.schemas.chat import ChatMessage
from app.compression.base import BaseCompressionStage, StageConfigField, CompressionContext, StageExecutionResult
from app.compression.preservation import PreservationGuards
from app.compression.tokenizer import count_messages_tokens

class CavemanStage(BaseCompressionStage):
    id = "caveman"
    name = "Caveman (Prose Simplification)"
    description = "Лингвистическое правиловое сжатие прозы (удаление вежливостей, вводных слов и канцеляризмов)."
    icon = "MessageSquareDashed"
    default_order = 20
    default_enabled = True
    is_builtin = True

    # English & Russian rule dictionary: (pattern, replacement, intensity_level)
    # levels: 1 = lite, 2 = full, 3 = ultra
    RULES: List[Tuple[re.Pattern, str, int]] = [
        # Pleasantries & greeting filler (lite/full)
        (re.compile(r'\b(?:sure|certainly|of course|absolutely),?\s*', re.I), '', 1),
        (re.compile(r'\b(?:happy to help|glad to help|no problem|you\'re welcome)[.!?,]?\s*', re.I), '', 1),
        (re.compile(r'\b(?:конечно|безусловно|с радостью помогу|всегда пожалуйста)[.!?,]?\s*', re.I), '', 1),
        (re.compile(r'\b(?:здравствуйте|добрый день|привет)[.!?,]?\s*', re.I), '', 1),

        # Polite framing & modal hedging
        (re.compile(r'\b(?:could you please|would you please|can you please|please kindly|please)\s*', re.I), '', 1),
        (re.compile(r'\b(?:пожалуйста|будьте добры|не могли бы вы)\s*', re.I), '', 1),
        (re.compile(r'\b(?:it is important to note that|note that|keep in mind that)\s*', re.I), '', 2),
        (re.compile(r'\b(?:важно отметить, что|обратите внимание, что|следует учитывать, что)\s*', re.I), '', 2),
        (re.compile(r'\b(?:as (?:mentioned|stated|discussed) (?:earlier|above|previously))\s*,?\s*', re.I), '', 2),
        (re.compile(r'\b(?:как (?:уже|было)?\s*(?:упоминалось|сказано|отмечено) ранее)\s*,?\s*', re.I), '', 2),

        # Wordy phrasing replacements (full)
        (re.compile(r'\b(?:due to the fact that|owing to the fact that)\b', re.I), 'because', 2),
        (re.compile(r'\b(?:в связи с тем, что|по причине того, что)\b', re.I), 'так как', 2),
        (re.compile(r'\b(?:in order to)\b', re.I), 'to', 2),
        (re.compile(r'\b(?:для того чтобы|с целью)\b', re.I), 'чтобы', 2),
        (re.compile(r'\b(?:at this point in time)\b', re.I), 'now', 2),
        (re.compile(r'\b(?:в данный момент времени|на сегодняшний день)\b', re.I), 'сейчас', 2),
        (re.compile(r'\b(?:a large number of)\b', re.I), 'many', 2),
        (re.compile(r'\b(?:большое количество)\b', re.I), 'много', 2),

        # Ultra aggressive filler removals (ultra)
        (re.compile(r'\b(?:i think that|i believe that|in my opinion|it seems that)\s*', re.I), '', 3),
        (re.compile(r'\b(?:я думаю, что|по моему мнению|мне кажется, что)\s*', re.I), '', 3),
        (re.compile(r'\b(?:basically|essentially|actually|literally)\s*', re.I), '', 3),
        (re.compile(r'\b(?:в основном|по сути|фактически|собственно говоря)\s*', re.I), '', 3),
    ]

    def get_config_schema(self) -> List[StageConfigField]:
        return [
            StageConfigField(
                key="intensity",
                label="Уровень интенсивности",
                type="select",
                default_value="full",
                options=[
                    {"label": "Lite (только вежливости и приветствия)", "value": "lite"},
                    {"label": "Full (вводные слова и канцелярские обороты)", "value": "full"},
                    {"label": "Ultra (максимальное удаление филлеров)", "value": "ultra"},
                ],
                description="Степень сокращения разговорных конструкций",
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

        intensity_str = str(config.get("intensity", "full")).lower()
        level_map = {"lite": 1, "full": 2, "ultra": 3}
        target_level = level_map.get(intensity_str, 2)

        active_rules = [(pat, repl) for pat, repl, lvl in self.RULES if lvl <= target_level]

        compressed_messages: List[ChatMessage] = []
        rules_applied_count = 0

        for msg in messages:
            if msg.role in {"system", "developer", "user", "tool", "function"} or not isinstance(msg.content, str):
                compressed_messages.append(msg)
                continue

            content = msg.content
            # Guard code blocks, URLs, and math
            text_with_sentinels, preserved_blocks = PreservationGuards.extract(content)

            orig_transformed = text_with_sentinels
            for pat, repl in active_rules:
                text_with_sentinels, count = pat.subn(repl, text_with_sentinels)
                rules_applied_count += count

            # Clean any resulting double spaces
            text_with_sentinels = re.sub(r'[ \t]{2,}', ' ', text_with_sentinels)

            restored = PreservationGuards.restore(text_with_sentinels, preserved_blocks)
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
            compressed=rules_applied_count > 0 and final_tokens < initial_tokens,
            tokens_before=initial_tokens,
            tokens_after=final_tokens,
            savings_percent=savings,
            duration_ms=duration,
            rules_applied=[f"caveman_rules_applied:{rules_applied_count}"] if rules_applied_count > 0 else [],
        )
