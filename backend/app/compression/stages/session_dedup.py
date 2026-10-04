import hashlib
import time
from typing import Any, Dict, List
from app.schemas.chat import ChatMessage
from app.compression.base import BaseCompressionStage, StageConfigField, CompressionContext, StageExecutionResult
from app.compression.tokenizer import count_messages_tokens

class SessionDedupStage(BaseCompressionStage):
    id = "session_dedup"
    name = "Session Dedup"
    description = "Кросс-диалоговая дедупликация повторяющихся блоков текста и файлов без потерь."
    icon = "CopyMinus"
    default_order = 3
    default_enabled = True
    is_builtin = True

    def get_config_schema(self) -> List[StageConfigField]:
        return [
            StageConfigField(
                key="min_block_chars",
                label="Мин. символов в блоке",
                type="number",
                default_value=80,
                min_value=30,
                max_value=2000,
                description="Минимальная длина блока для поиска повторений",
            ),
            StageConfigField(
                key="min_block_lines",
                label="Мин. строк в блоке",
                type="number",
                default_value=3,
                min_value=2,
                max_value=20,
                description="Минимальное количество строк для дедупликации",
            ),
        ]

    def _extract_blocks(self, text: str, min_chars: int, min_lines: int) -> List[str]:
        candidates: List[str] = []
        # 1. Whole text
        trimmed = text.strip()
        if len(trimmed) >= min_chars and len(trimmed.splitlines()) >= min_lines:
            candidates.append(trimmed)

        # 2. Paragraphs
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) >= min_chars and len(p.strip().splitlines()) >= min_lines]
        for p in paragraphs:
            if p not in candidates:
                candidates.append(p)

        # 3. Multiline chunks (from any line to end)
        lines = text.splitlines()
        if len(lines) >= min_lines:
            for i in range(len(lines) - min_lines + 1):
                chunk = "\n".join(lines[i:])
                if len(chunk) >= min_chars and chunk not in candidates:
                    candidates.append(chunk)

        # Sort longest first
        candidates.sort(key=lambda s: len(s), reverse=True)
        return candidates

    async def compress(
        self,
        messages: List[ChatMessage],
        config: Dict[str, Any],
        context: CompressionContext,
    ) -> StageExecutionResult:
        t0 = time.perf_counter()
        initial_tokens = count_messages_tokens(messages)

        min_chars = int(config.get("min_block_chars", 80))
        min_lines = int(config.get("min_block_lines", 3))

        seen_blocks: Dict[str, str] = {}  # hash -> first_seen_ref
        compressed_messages: List[ChatMessage] = []
        replaced_count = 0

        # Preserve recent turns
        num_msgs = len(messages)
        preserve_start = max(0, num_msgs - (context.preserve_recent_turns * 2)) if context.preserve_recent_turns > 0 else num_msgs

        for idx, msg in enumerate(messages):
            if msg.role == "system" or not isinstance(msg.content, str) or idx >= preserve_start:
                if isinstance(msg.content, str):
                    for b in self._extract_blocks(msg.content, min_chars, min_lines):
                        h = hashlib.sha256(b.encode("utf-8")).hexdigest()[:8]
                        if h not in seen_blocks:
                            seen_blocks[h] = f"sha={h}"
                compressed_messages.append(msg)
                continue

            content = msg.content
            # Check whole message duplicate
            content_hash = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()[:8]
            if content_hash in seen_blocks:
                replaced_count += 1
                new_msg = ChatMessage(
                    role=msg.role,
                    content=f"[dedup:ref sha={content_hash} (identical to earlier message)]",
                    name=msg.name,
                )
                compressed_messages.append(new_msg)
                continue

            # Scan for candidate block duplicates
            modified_content = content
            blocks = self._extract_blocks(content, min_chars, min_lines)
            for b in blocks:
                b_hash = hashlib.sha256(b.encode("utf-8")).hexdigest()[:8]
                if b_hash in seen_blocks:
                    if b in modified_content:
                        modified_content = modified_content.replace(b, f"[dedup:block sha={b_hash}]")
                        replaced_count += 1
                else:
                    seen_blocks[b_hash] = f"sha={b_hash}"

            compressed_messages.append(ChatMessage(role=msg.role, content=modified_content, name=msg.name))

        final_tokens = count_messages_tokens(compressed_messages)
        savings = max(0.0, round(((initial_tokens - final_tokens) / max(1, initial_tokens)) * 100, 2))
        duration = round((time.perf_counter() - t0) * 1000, 2)

        return StageExecutionResult(
            stage_id=self.id,
            stage_name=self.name,
            messages=compressed_messages,
            compressed=replaced_count > 0 and final_tokens < initial_tokens,
            tokens_before=initial_tokens,
            tokens_after=final_tokens,
            savings_percent=savings,
            duration_ms=duration,
            rules_applied=[f"dedup_blocks_replaced:{replaced_count}"] if replaced_count > 0 else [],
        )
