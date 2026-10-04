import hashlib
import time
from typing import Any, Dict, List
from app.schemas.chat import ChatMessage
from app.compression.base import BaseCompressionStage, StageConfigField, CompressionContext, StageExecutionResult
from app.compression.tokenizer import count_messages_tokens

# Simple bounded in-memory store for CCR retrieved blocks
_CCR_STORE: Dict[str, str] = {}
_MAX_CCR_STORE_SIZE = 5000

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
        t0 = time.perf_counter()
        initial_tokens = count_messages_tokens(messages)

        min_chars = int(config.get("min_chars", 600))
        max_blocks = int(config.get("max_blocks_per_turn", 3))

        num_msgs = len(messages)
        # Protect system and recent turns
        preserve_start = max(0, num_msgs - max(1, context.preserve_recent_turns * 2))

        compressed_messages: List[ChatMessage] = []
        archived_count = 0

        for idx, msg in enumerate(messages):
            if msg.role == "system" or not isinstance(msg.content, str) or idx >= preserve_start:
                compressed_messages.append(msg)
                continue

            content = msg.content
            if len(content) < min_chars:
                compressed_messages.append(msg)
                continue

            # If the entire message content is huge
            if len(content) >= min_chars and "\n\n" not in content:
                block_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:24]
                self._store_block(block_hash, content)
                marker = f"[CCR retrieve hash={block_hash} chars={len(content)}]"
                compressed_messages.append(msg.model_copy(update={"content": marker}))
                archived_count += 1
                continue

            # Split paragraphs
            paragraphs = content.split("\n\n")
            modified_paragraphs = []
            turn_archived = 0

            for p in paragraphs:
                if len(p) >= min_chars and turn_archived < max_blocks:
                    block_hash = hashlib.sha256(p.encode("utf-8")).hexdigest()[:24]
                    self._store_block(block_hash, p)
                    marker = f"[CCR retrieve hash={block_hash} chars={len(p)}]"
                    modified_paragraphs.append(marker)
                    turn_archived += 1
                    archived_count += 1
                else:
                    modified_paragraphs.append(p)

            new_content = "\n\n".join(modified_paragraphs)
            compressed_messages.append(msg.model_copy(update={"content": new_content}))

        final_tokens = count_messages_tokens(compressed_messages)
        savings = max(0.0, round(((initial_tokens - final_tokens) / max(1, initial_tokens)) * 100, 2))
        duration = round((time.perf_counter() - t0) * 1000, 2)

        return StageExecutionResult(
            stage_id=self.id,
            stage_name=self.name,
            messages=compressed_messages,
            compressed=archived_count > 0 and final_tokens < initial_tokens,
            tokens_before=initial_tokens,
            tokens_after=final_tokens,
            savings_percent=savings,
            duration_ms=duration,
            rules_applied=[f"ccr_archived_blocks:{archived_count}"] if archived_count > 0 else [],
        )

    def _store_block(self, block_hash: str, text: str) -> None:
        global _CCR_STORE
        if len(_CCR_STORE) >= _MAX_CCR_STORE_SIZE:
            # Purge oldest 1000 items
            keys_to_del = list(_CCR_STORE.keys())[:1000]
            for k in keys_to_del:
                _CCR_STORE.pop(k, None)
        _CCR_STORE[block_hash] = text
