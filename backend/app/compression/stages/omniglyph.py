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
        tokens = count_messages_tokens(messages)
        return StageExecutionResult(stage_id=self.id, stage_name=self.name,
                                    messages=messages, tokens_before=tokens, tokens_after=tokens,
                                    warning='OmniGlyph rendering is not implemented; original text preserved')
