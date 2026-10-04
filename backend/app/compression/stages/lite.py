import re
import time
from typing import Any, Dict, List
from app.schemas.chat import ChatMessage
from app.compression.base import BaseCompressionStage, StageConfigField, CompressionContext, StageExecutionResult
from app.compression.tokenizer import count_messages_tokens

class LiteStage(BaseCompressionStage):
    id = "lite"
    name = "Lite (Format Cleanup)"
    description = "Безопасная очистка пробелов, схлопывание множественных пустых строк и удаление дублей системных промптов."
    icon = "Sparkles"
    default_order = 5
    default_enabled = True
    is_builtin = True

    MULTIPLE_NEWLINES_RE = re.compile(r'\n{3,}')
    TRAILING_WHITESPACE_RE = re.compile(r'[ \t]+$', re.MULTILINE)
    BASE64_IMAGE_RE = re.compile(r'data:image\/[a-zA-Z]+;base64,[A-Za-z0-9+/=]{100,}')

    def get_config_schema(self) -> List[StageConfigField]:
        return [
            StageConfigField(
                key="collapse_whitespace",
                label="Схлопывать пустые строки",
                type="boolean",
                default_value=True,
                description="Превращать 3 и более пустых строк подряд в двойной перенос",
            ),
            StageConfigField(
                key="trim_trailing_spaces",
                label="Удалять хвостовые пробелы",
                type="boolean",
                default_value=True,
                description="Удалять незначащие пробелы в концах строк",
            ),
            StageConfigField(
                key="dedup_system_prompts",
                label="Дедуплицировать System Prompts",
                type="boolean",
                default_value=True,
                description="Удалять дубликаты системных инструкций, если они повторяются",
            ),
            StageConfigField(
                key="strip_non_vision_images",
                label="Удалять base64-изображения для text-only моделей",
                type="boolean",
                default_value=True,
                description="Заменять base64-картинки на текстовые маркеры, если модель не поддерживает Vision",
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

        do_collapse = config.get("collapse_whitespace", True)
        do_trim = config.get("trim_trailing_spaces", True)
        do_dedup_system = config.get("dedup_system_prompts", True)
        do_strip_images = config.get("strip_non_vision_images", True) and not context.supports_vision

        compressed_messages: List[ChatMessage] = []
        seen_system_prompts = set()
        modified = False
        rules_applied = []

        for msg in messages:
            if msg.role == "system" and do_dedup_system and isinstance(msg.content, str):
                cleaned_sys = msg.content.strip()
                if cleaned_sys in seen_system_prompts:
                    modified = True
                    rules_applied.append("dedup_system_prompt")
                    continue
                seen_system_prompts.add(cleaned_sys)

            if isinstance(msg.content, str):
                content = msg.content
                orig = content

                if do_trim:
                    content = self.TRAILING_WHITESPACE_RE.sub('', content)
                if do_collapse:
                    content = self.MULTIPLE_NEWLINES_RE.sub('\n\n', content)
                if do_strip_images and "data:image" in content:
                    content = self.BASE64_IMAGE_RE.sub('[image:stripped_non_vision]', content)

                if content != orig:
                    modified = True
                    compressed_messages.append(msg.model_copy(update={"content": content}))
                else:
                    compressed_messages.append(msg)
            elif isinstance(msg.content, list):
                # Multipart content
                new_parts = []
                for part in msg.content:
                    if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                        t_val = part["text"]
                        if do_trim:
                            t_val = self.TRAILING_WHITESPACE_RE.sub('', t_val)
                        if do_collapse:
                            t_val = self.MULTIPLE_NEWLINES_RE.sub('\n\n', t_val)
                        new_parts.append({**part, "text": t_val})
                        if t_val != part["text"]:
                            modified = True
                    elif isinstance(part, dict) and part.get("type") == "image_url" and do_strip_images:
                        new_parts.append({"type": "text", "text": "[image:stripped_non_vision]"})
                        modified = True
                    else:
                        new_parts.append(part)
                compressed_messages.append(msg.model_copy(update={"content": new_parts}))
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
            rules_applied=rules_applied,
        )
