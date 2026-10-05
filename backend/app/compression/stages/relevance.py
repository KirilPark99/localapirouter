import re
import time
from typing import Any, Dict, List, Set
from app.schemas.chat import ChatMessage
from app.compression.base import BaseCompressionStage, StageConfigField, CompressionContext, StageExecutionResult
from app.compression.preservation import PreservationGuards
from app.compression.tokenizer import count_messages_tokens

class RelevanceStage(BaseCompressionStage):
    id = "relevance"
    name = "Relevance (Extractive Query Scoring)"
    description = "Экстрактивная оценка релевантности предложений к последней задаче пользователя."
    icon = "Filter"
    default_order = 18
    default_enabled = True
    is_builtin = True

    # Sentence boundary regex (preserving whitespace)
    SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')
    # Force-preserve signals: digits, URLs, errors, code indicators, file paths
    FORCE_PRESERVE_RE = re.compile(
        r'(\d|https?://|error|exception|failure|traceback|def |class |import |```|/[\w.-]+/|\w+\.\w{1,4}\b)',
        re.IGNORECASE
    )

    def get_config_schema(self) -> List[StageConfigField]:
        return [
            StageConfigField(
                key="budget_ratio",
                label="Целевой бюджет сохранения",
                type="number",
                default_value=0.8,
                min_value=0.3,
                max_value=1.0,
                description="Доля текста, оставляемая после оценки релевантности (0.8 = 80% объема)",
            ),
            StageConfigField(
                key="min_sentences_to_prune",
                label="Мин. предложений в сообщении",
                type="number",
                default_value=5,
                min_value=2,
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

        budget_ratio = float(config.get("budget_ratio", 0.8))
        min_sentences = int(config.get("min_sentences_to_prune", 5))

        # Extract latest user query terms
        query_words = self._extract_query_words(messages)
        if not query_words and context.metadata.get("latest_user_query"):
            query_words = self._extract_query_words([ChatMessage(role="user", content=context.metadata["latest_user_query"])])
        if not query_words:
            return StageExecutionResult(
                stage_id=self.id,
                stage_name=self.name,
                messages=messages,
                compressed=False,
                tokens_before=initial_tokens,
                tokens_after=initial_tokens,
            )

        num_msgs = len(messages)
        preserve_start = max(0, num_msgs - max(1, context.preserve_recent_turns * 2))

        compressed_messages: List[ChatMessage] = []
        sentences_dropped = 0

        for idx, msg in enumerate(messages):
            if msg.role in {"system", "developer", "user", "tool", "function"} or not isinstance(msg.content, str) or idx >= preserve_start:
                compressed_messages.append(msg)
                continue

            if PreservationGuards.extract(msg.content)[1]:
                compressed_messages.append(msg)
                continue
            content = msg.content
            sentences = self.SENTENCE_SPLIT_RE.split(content)
            if len(sentences) < min_sentences:
                compressed_messages.append(msg)
                continue

            scored_sentences = []
            for s_idx, s in enumerate(sentences):
                # Check force preserve
                is_forced = bool(self.FORCE_PRESERVE_RE.search(s))
                score = 100.0 if is_forced else self._score_sentence(s, query_words)
                scored_sentences.append({"idx": s_idx, "text": s, "score": score, "forced": is_forced})

            # Calculate target count
            target_keep_count = max(2, int(len(sentences) * budget_ratio))
            # Sort by score descending
            sorted_by_score = sorted(scored_sentences, key=lambda x: x["score"], reverse=True)
            keep_indices = set(x["idx"] for x in sorted_by_score[:target_keep_count])
            # Also keep all forced
            for x in scored_sentences:
                if x["forced"]:
                    keep_indices.add(x["idx"])

            if len(keep_indices) < len(sentences):
                sentences_dropped += (len(sentences) - len(keep_indices))
                retained_sentences = [s for s_idx, s in enumerate(sentences) if s_idx in keep_indices]
                compressed_messages.append(msg.model_copy(update={"content": " ".join(retained_sentences)}))
            else:
                compressed_messages.append(msg)

        final_tokens = count_messages_tokens(compressed_messages)
        savings = max(0.0, round(((initial_tokens - final_tokens) / max(1, initial_tokens)) * 100, 2))
        duration = round((time.perf_counter() - t0) * 1000, 2)

        return StageExecutionResult(
            stage_id=self.id,
            stage_name=self.name,
            messages=compressed_messages,
            compressed=sentences_dropped > 0 and final_tokens < initial_tokens,
            tokens_before=initial_tokens,
            tokens_after=final_tokens,
            savings_percent=savings,
            duration_ms=duration,
            rules_applied=[f"sentences_dropped:{sentences_dropped}"] if sentences_dropped > 0 else [],
        )

    def _extract_query_words(self, messages: List[ChatMessage]) -> Set[str]:
        # Search for last user message
        for msg in reversed(messages):
            if msg.role == "user" and isinstance(msg.content, str):
                words = re.findall(r'\b[a-zA-Zа-яА-Я0-9_]{3,}\b', msg.content.lower())
                return set(words)
        return set()

    def _score_sentence(self, sentence: str, query_words: Set[str]) -> float:
        s_words = re.findall(r'\b[a-zA-Zа-яА-Я0-9_]{3,}\b', sentence.lower())
        if not s_words:
            return 0.0
        overlap = sum(1 for w in s_words if w in query_words)
        return (overlap / len(s_words)) * 10.0
