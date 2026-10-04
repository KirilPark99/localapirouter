import re
import time
from typing import Any, Dict, List
from app.schemas.chat import ChatMessage
from app.compression.base import BaseCompressionStage, StageConfigField, CompressionContext, StageExecutionResult
from app.compression.preservation import PreservationGuards
from app.compression.tokenizer import count_messages_tokens

class UltraStage(BaseCompressionStage):
    id = "ultra"
    name = "Ultra (Heuristic Pruning & Hard Budget)"
    description = "Экстремальный эвристический прунинг токенов для ситуаций, когда контекст превышает лимиты окна модели."
    icon = "Flame"
    default_order = 40
    default_enabled = False  # Disabled by default, opt-in for emergency headroom
    is_builtin = True

    FORCE_PRESERVE_TOKEN_RE = re.compile(r'(\d|https?://|[._/\\#=]|Error:|Exception:|```|\bdef\b|\bclass\b)')

    def get_config_schema(self) -> List[StageConfigField]:
        return [
            StageConfigField(
                key="target_keep_rate",
                label="Доля сохраняемых токенов",
                type="number",
                default_value=0.6,
                min_value=0.2,
                max_value=0.95,
                description="Доля оставляемых токенов в прозе (0.6 = сжатие на 40%)",
            ),
            StageConfigField(
                key="hard_token_limit",
                label="Жесткий лимит токенов (0 = выкл)",
                type="number",
                default_value=0,
                min_value=0,
                max_value=128000,
                description="Если промпт превышает это число токенов, обрезать старую историю до лимита",
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

        keep_rate = float(config.get("target_keep_rate", 0.6))
        hard_limit = int(config.get("hard_token_limit", 0))

        compressed_messages: List[ChatMessage] = []
        tokens_pruned = 0

        # Protect recent turns
        num_msgs = len(messages)
        preserve_start = max(0, num_msgs - max(1, context.preserve_recent_turns * 2))

        for idx, msg in enumerate(messages):
            if msg.role == "system" or not isinstance(msg.content, str) or idx >= preserve_start:
                compressed_messages.append(msg)
                continue

            content = msg.content
            text_with_sentinels, preserved_blocks = PreservationGuards.extract(content)

            # Prune words
            tokens = re.split(r'(\s+)', text_with_sentinels)
            word_tokens = [t for t in tokens if not t.isspace()]
            target_keep = int(len(word_tokens) * keep_rate)

            # Score tokens
            scored = []
            for w_idx, w in enumerate(word_tokens):
                score = self._score_token(w)
                scored.append((w_idx, w, score))

            # Lowest scores pruned first
            scored_sorted = sorted(scored, key=lambda x: x[2])
            to_prune_indices = set()
            pruned_count = 0
            max_prune = len(word_tokens) - target_keep

            for w_idx, w, score in scored_sorted:
                if pruned_count >= max_prune:
                    break
                if score < 0.8:
                    to_prune_indices.add(w_idx)
                    pruned_count += 1

            tokens_pruned += pruned_count

            # Rebuild text
            word_counter = 0
            new_tokens = []
            for t in tokens:
                if t.isspace() or "\u0000" in t:
                    new_tokens.append(t)
                else:
                    if word_counter not in to_prune_indices:
                        new_tokens.append(t)
                    word_counter += 1

            pruned_text = "".join(new_tokens)
            restored = PreservationGuards.restore(pruned_text, preserved_blocks)
            compressed_messages.append(msg.model_copy(update={"content": restored}))

        # Check hard token limit post-pass
        current_tokens = count_messages_tokens(compressed_messages)
        if hard_limit > 0 and current_tokens > hard_limit:
            compressed_messages = self._apply_hard_limit(compressed_messages, hard_limit, context.preserve_recent_turns)

        final_tokens = count_messages_tokens(compressed_messages)
        savings = max(0.0, round(((initial_tokens - final_tokens) / max(1, initial_tokens)) * 100, 2))
        duration = round((time.perf_counter() - t0) * 1000, 2)

        return StageExecutionResult(
            stage_id=self.id,
            stage_name=self.name,
            messages=compressed_messages,
            compressed=final_tokens < initial_tokens,
            tokens_before=initial_tokens,
            tokens_after=final_tokens,
            savings_percent=savings,
            duration_ms=duration,
            rules_applied=[f"ultra_tokens_pruned:{tokens_pruned}"] if tokens_pruned > 0 else [],
        )

    def _score_token(self, token: str) -> float:
        if self.FORCE_PRESERVE_TOKEN_RE.search(token):
            return 1.0
        if len(token) <= 2:
            return 0.2
        if token[0].isupper():
            return 0.8
        if len(token) >= 7:
            return 0.7
        return 0.5

    def _apply_hard_limit(self, messages: List[ChatMessage], limit: int, preserve_turns: int) -> List[ChatMessage]:
        # Drop oldest non-system messages until under limit
        res = list(messages)
        while len(res) > (preserve_turns * 2 + 1) and count_messages_tokens(res) > limit:
            # Find first non-system message
            drop_idx = None
            for i, m in enumerate(res):
                if m.role != "system":
                    drop_idx = i
                    break
            if drop_idx is not None:
                res.pop(drop_idx)
            else:
                break
        return res
