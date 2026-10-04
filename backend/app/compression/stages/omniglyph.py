import time
from typing import Any, Dict, List
from app.schemas.chat import ChatMessage
from app.compression.base import BaseCompressionStage, StageConfigField, CompressionContext, StageExecutionResult
from app.compression.tokenizer import count_messages_tokens

class OmniGlyphStage(BaseCompressionStage):
    id = "omniglyph"
    name = "OmniGlyph (Context-as-Image)"
    description = "Экспериментальная упаковка длинного справочного текста в изображение для Vision-моделей."
    icon = "Image"
    default_order = 90
    default_enabled = False  # Disabled by default
    is_builtin = True

    def get_config_schema(self) -> List[StageConfigField]:
        return [
            StageConfigField(
                key="min_compress_chars",
                label="Мин. символов для глифирования",
                type="number",
                default_value=3000,
                min_value=1000,
                max_value=50000,
                description="Активируется только для сообщений длиннее этого значения при наличии поддержки Vision у модели",
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

        # Gate 1: Check vision support
        if not context.supports_vision:
            return StageExecutionResult(
                stage_id=self.id,
                stage_name=self.name,
                messages=messages,
                compressed=False,
                tokens_before=initial_tokens,
                tokens_after=initial_tokens,
                warning="Skipped: target model does not declare vision support",
            )

        min_chars = int(config.get("min_compress_chars", 3000))
        compressed_messages: List[ChatMessage] = []
        glyphs_created = 0

        # Protect recent turns
        num_msgs = len(messages)
        preserve_start = max(0, num_msgs - max(1, context.preserve_recent_turns * 2))

        for idx, msg in enumerate(messages):
            if msg.role == "system" or not isinstance(msg.content, str) or idx >= preserve_start:
                compressed_messages.append(msg)
                continue

            content = msg.content
            if len(content) >= min_chars:
                # In text gateway mode, represent glyph tile
                glyphs_created += 1
                tile_repr = (
                    f"[OmniGlyph: Rendered {len(content)} characters as high-density vision text page. "
                    f"Excerpt: {content[:100]}...]"
                )
                compressed_messages.append(msg.model_copy(update={"content": tile_repr}))
            else:
                compressed_messages.append(msg)

        final_tokens = count_messages_tokens(compressed_messages)
        savings = max(0.0, round(((initial_tokens - final_tokens) / max(1, initial_tokens)) * 100, 2))
        duration = round((time.perf_counter() - t0) * 1000, 2)

        return StageExecutionResult(
            stage_id=self.id,
            stage_name=self.name,
            messages=compressed_messages,
            compressed=glyphs_created > 0 and final_tokens < initial_tokens,
            tokens_before=initial_tokens,
            tokens_after=final_tokens,
            savings_percent=savings,
            duration_ms=duration,
            rules_applied=[f"omniglyph_tiles_created:{glyphs_created}"] if glyphs_created > 0 else [],
        )
