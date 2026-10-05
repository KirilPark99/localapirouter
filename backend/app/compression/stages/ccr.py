from typing import Any, Dict, List
from app.schemas.chat import ChatMessage
from app.compression.base import BaseCompressionStage, StageConfigField, CompressionContext, StageExecutionResult
from app.compression.tokenizer import count_messages_tokens

class CcrStage(BaseCompressionStage):
    id = "ccr"
    name = "CCR (Retrieval Archive)"
    description = "Архивация крупных блоков текста в историческом контексте с заменой на маркеры извлечения."
    icon = "Archive"
    default_order = 4
    default_enabled = True
    is_builtin = True

    def get_config_schema(self) -> List[StageConfigField]:
        return [
            StageConfigField(
                key="min_chars",
                label="Мин. размер блока (символов)",
                type="number",
                default_value=600,
                min_value=200,
                max_value=10000,
                description="Блоки длиннее этого значения будут архивироваться в старых репликах",
            ),
            StageConfigField(
                key="max_blocks_per_turn",
                label="Макс. блоков на сообщение",
                type="number",
                default_value=3,
                min_value=1,
                max_value=20,
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
                                    warning='CCR retrieval is not implemented; original text preserved')
