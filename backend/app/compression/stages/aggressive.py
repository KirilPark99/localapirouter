import re
import time
from typing import Any, Dict, List
from app.schemas.chat import ChatMessage
from app.compression.base import BaseCompressionStage, StageConfigField, CompressionContext, StageExecutionResult
from app.compression.tokenizer import count_messages_tokens

class AggressiveStage(BaseCompressionStage):
    id = "aggressive"
    name = "Aggressive (Progressive Aging)"
    description = "Прогрессивное старение диалога: суммаризация глубокой истории в тезисы с сохранением свежих реплик."
    icon = "History"
    default_order = 30
    default_enabled = True
    is_builtin = True

    def get_config_schema(self) -> List[StageConfigField]:
        return [
            StageConfigField(
                key="recent_turns_verbatim",
                label="Реплик без изменений (Verbatim)",
                type="number",
                default_value=4,
                min_value=1,
                max_value=20,
                description="Количество последних сообщений, которые остаются полностью неизменными",
            ),
            StageConfigField(
                key="summarize_depth",
                label="Порог суммаризации (глубина реплик)",
                type="number",
                default_value=8,
                min_value=3,
                max_value=50,
                description="Сообщения старше этой глубины сворачиваются в краткие тезисы",
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

        recent_n = int(config.get("recent_turns_verbatim", 4))
        sum_depth = int(config.get("summarize_depth", 8))

        total_msgs = len(messages)
        if total_msgs <= recent_n:
            return StageExecutionResult(
                stage_id=self.id,
                stage_name=self.name,
                messages=messages,
                compressed=False,
                tokens_before=initial_tokens,
                tokens_after=initial_tokens,
            )

        compressed_messages: List[ChatMessage] = []
        summarized_count = 0

        # Boundary indices:
        # 0 .. (total_msgs - sum_depth): Deep history -> Summarize
        # (total_msgs - sum_depth) .. (total_msgs - recent_n): Middle -> Truncate lines
        # (total_msgs - recent_n) .. total_msgs: Recent -> Verbatim
        deep_boundary = max(0, total_msgs - sum_depth)
        recent_boundary = max(0, total_msgs - recent_n)

        for idx, msg in enumerate(messages):
            if msg.role == "system" or not isinstance(msg.content, str):
                compressed_messages.append(msg)
                continue

            content = msg.content
            if idx >= recent_boundary:
                # Verbatim recent
                compressed_messages.append(msg)
            elif idx < deep_boundary:
                # Deep history: summarize to key bullets
                summary = self._summarize_message(content, msg.role)
                if len(summary) < len(content):
                    summarized_count += 1
                    compressed_messages.append(ChatMessage(role=msg.role, content=summary, name=msg.name))
                else:
                    compressed_messages.append(msg)
            else:
                # Middle history: compact paragraphs
                compacted = self._compact_middle(content)
                if len(compacted) < len(content):
                    summarized_count += 1
                    compressed_messages.append(ChatMessage(role=msg.role, content=compacted, name=msg.name))
                else:
                    compressed_messages.append(msg)

        final_tokens = count_messages_tokens(compressed_messages)
        savings = max(0.0, round(((initial_tokens - final_tokens) / max(1, initial_tokens)) * 100, 2))
        duration = round((time.perf_counter() - t0) * 1000, 2)

        return StageExecutionResult(
            stage_id=self.id,
            stage_name=self.name,
            messages=compressed_messages,
            compressed=summarized_count > 0 and final_tokens < initial_tokens,
            tokens_before=initial_tokens,
            tokens_after=final_tokens,
            savings_percent=savings,
            duration_ms=duration,
            rules_applied=[f"turns_aged_or_summarized:{summarized_count}"] if summarized_count > 0 else [],
        )

    def _summarize_message(self, text: str, role: str) -> str:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if len(lines) <= 2 and len(text) < 250:
            return text

        # Extract first line / key intent and errors/actions
        key_points = []
        if lines:
            key_points.append(lines[0][:150])

        for line in lines[1:]:
            if any(k in line.lower() for k in ["error", "exception", "failed", "fixed", "done", "created", "result", "file", "path"]):
                key_points.append(line[:120])
            if len(key_points) >= 4:
                break

        bullets = "\n- ".join(key_points)
        return f"[COMPRESSED:summary ({role})]\n- {bullets}"

    def _compact_middle(self, text: str) -> str:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) <= 2:
            return text
        # Keep first and last paragraph, summarize middle if large
        if len(paragraphs) > 3:
            return f"{paragraphs[0]}\n\n[... {len(paragraphs) - 2} middle paragraphs compacted ...]\n\n{paragraphs[-1]}"
        return text
