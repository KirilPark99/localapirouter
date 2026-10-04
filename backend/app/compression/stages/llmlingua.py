import re
import time
from typing import Any, Dict, List
from app.schemas.chat import ChatMessage
from app.compression.base import BaseCompressionStage, StageConfigField, CompressionContext, StageExecutionResult
from app.compression.preservation import PreservationGuards
from app.compression.tokenizer import count_messages_tokens

class LlmLinguaStage(BaseCompressionStage):
    id = "llmlingua"
    name = "LLMLingua (Semantic Pruning)"
    description = "Семантический прунинг токенов с сохранением ключевого смысла (с полной защитой синтаксиса кода)."
    icon = "BrainCircuit"
    default_order = 35
    default_enabled = True
    is_builtin = True

    # Low-entropy filler and function words in English and Russian
    LOW_INFO_WORDS = {
        # EN
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "very", "really", "quite",
        "just", "also", "already", "simply", "definitely", "certainly",
        # RU
        "и", "в", "на", "с", "по", "у", "к", "о", "из", "за", "от", "до",
        "же", "ли", "бы", "то", "что", "как", "так", "это", "этот", "эта",
        "очень", "весьма", "просто", "действительно", "фактически", "также"
    }

    def get_config_schema(self) -> List[StageConfigField]:
        return [
            StageConfigField(
                key="prune_ratio",
                label="Доля сокращения токенов",
                type="number",
                default_value=0.25,
                min_value=0.05,
                max_value=0.6,
                description="Желаемый процент удаления низкоинформативных токенов (0.25 = 25%)",
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

        prune_ratio = float(config.get("prune_ratio", 0.25))
        compressed_messages: List[ChatMessage] = []
        tokens_pruned_count = 0

        # Preserve recent turns
        num_msgs = len(messages)
        preserve_start = max(0, num_msgs - max(1, context.preserve_recent_turns * 2))

        for idx, msg in enumerate(messages):
            if msg.role == "system" or not isinstance(msg.content, str) or idx >= preserve_start:
                compressed_messages.append(msg)
                continue

            content = msg.content
            # Guard code blocks, URLs, and formulas
            text_with_sentinels, preserved_blocks = PreservationGuards.extract(content)

            # Prune low info tokens from prose
            tokens = re.split(r'(\s+)', text_with_sentinels)
            word_tokens = [t for t in tokens if not t.isspace()]
            target_prune_count = int(len(word_tokens) * prune_ratio)

            pruned_so_far = 0
            new_tokens = []
            for t in tokens:
                if t.isspace() or "\u0000" in t:
                    new_tokens.append(t)
                    continue

                clean_w = re.sub(r'[^\w]', '', t).lower()
                # If it's a low info word and we haven't reached target
                if clean_w in self.LOW_INFO_WORDS and pruned_so_far < target_prune_count and len(t) <= 6:
                    pruned_so_far += 1
                    tokens_pruned_count += 1
                    continue

                new_tokens.append(t)

            pruned_text = "".join(new_tokens)
            restored = PreservationGuards.restore(pruned_text, preserved_blocks)
            compressed_messages.append(msg.model_copy(update={"content": restored}))

        final_tokens = count_messages_tokens(compressed_messages)
        savings = max(0.0, round(((initial_tokens - final_tokens) / max(1, initial_tokens)) * 100, 2))
        duration = round((time.perf_counter() - t0) * 1000, 2)

        return StageExecutionResult(
            stage_id=self.id,
            stage_name=self.name,
            messages=compressed_messages,
            compressed=tokens_pruned_count > 0 and final_tokens < initial_tokens,
            tokens_before=initial_tokens,
            tokens_after=final_tokens,
            savings_percent=savings,
            duration_ms=duration,
            rules_applied=[f"semantic_tokens_pruned:{tokens_pruned_count}"] if tokens_pruned_count > 0 else [],
        )
