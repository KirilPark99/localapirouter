import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import CompressionStage, CompressionGlobalSetting
from app.schemas.chat import ChatMessage
from app.compression.base import CompressionContext, StageExecutionResult
from app.compression.registry import StageRegistry
from app.compression.tokenizer import count_messages_tokens

logger = logging.getLogger(__name__)

from app.compression.caching_aware import should_preserve_system_prompt


class CompressionPipelineService:

    @classmethod
    async def get_global_settings(cls, db: AsyncSession) -> CompressionGlobalSetting:
        res = await db.execute(select(CompressionGlobalSetting).limit(1))
        settings = res.scalar_one_or_none()
        if not settings:
            settings = CompressionGlobalSetting(
                enabled=True,
                trigger_token_threshold=1000,
                min_savings_bailout_percent=0.0,
                preserve_recent_turns=1,
                preserve_system_prompt_mode="when_caching",
                enable_telemetry=True,
                fail_open=True,
            )
            db.add(settings)
            await db.commit()
            await db.refresh(settings)
        return settings

    @classmethod
    async def update_global_settings(cls, db: AsyncSession, data: Dict[str, Any]) -> CompressionGlobalSetting:
        settings = await cls.get_global_settings(db)
        if "enabled" in data:
            settings.enabled = bool(data["enabled"])
        if "trigger_token_threshold" in data:
            settings.trigger_token_threshold = int(data["trigger_token_threshold"])
        if "min_savings_bailout_percent" in data:
            settings.min_savings_bailout_percent = float(data["min_savings_bailout_percent"])
        if "preserve_recent_turns" in data:
            settings.preserve_recent_turns = int(data["preserve_recent_turns"])
        if "preserve_system_prompt_mode" in data:
            settings.preserve_system_prompt_mode = str(data["preserve_system_prompt_mode"])
        if "enable_telemetry" in data:
            settings.enable_telemetry = bool(data["enable_telemetry"])
        if "fail_open" in data:
            settings.fail_open = bool(data["fail_open"])

        await db.commit()
        await db.refresh(settings)
        return settings

    @classmethod
    async def get_stages(cls, db: AsyncSession) -> List[CompressionStage]:
        res = await db.execute(select(CompressionStage).order_by(CompressionStage.priority_order.asc()))
        return list(res.scalars().all())

    @classmethod
    async def update_stage(cls, db: AsyncSession, stage_id: str, data: Dict[str, Any]) -> Optional[CompressionStage]:
        res = await db.execute(select(CompressionStage).where(CompressionStage.id == stage_id))
        stage = res.scalar_one_or_none()
        if not stage:
            return None

        if "enabled" in data:
            stage.enabled = bool(data["enabled"])
        if "priority_order" in data:
            stage.priority_order = int(data["priority_order"])
        if "config_json" in data:
            stage.config_json = data["config_json"]
        if "name" in data and not stage.is_builtin:
            stage.name = str(data["name"])
        if "description" in data and not stage.is_builtin:
            stage.description = str(data["description"])
        if "custom_rules" in data:
            stage.custom_rules = data["custom_rules"]

        await db.commit()
        await db.refresh(stage)
        return stage

    @classmethod
    async def reorder_stages(cls, db: AsyncSession, ordered_ids: List[str]) -> List[CompressionStage]:
        for idx, s_id in enumerate(ordered_ids, start=1):
            res = await db.execute(select(CompressionStage).where(CompressionStage.id == s_id))
            stage = res.scalar_one_or_none()
            if stage:
                stage.priority_order = idx
        await db.commit()
        return await cls.get_stages(db)

    @classmethod
    async def create_custom_stage(cls, db: AsyncSession, data: Dict[str, Any]) -> CompressionStage:
        stage_id = data.get("id") or f"custom_{int(time.time())}"
        name = data.get("name") or "Пользовательский этап"
        description = data.get("description") or "Пользовательские правила сжатия"
        icon = data.get("icon") or "Sliders"
        priority_order = int(data.get("priority_order", 50))
        rules = data.get("rules", [])

        config_json = {"rules": rules, "guard_code_blocks": data.get("guard_code_blocks", True)}

        stage = CompressionStage(
            id=stage_id,
            name=name,
            description=description,
            icon=icon,
            stage_type="custom_regex",
            priority_order=priority_order,
            enabled=True,
            is_builtin=False,
            config_json=config_json,
            custom_rules=rules,
        )
        db.add(stage)
        await db.commit()
        await db.refresh(stage)
        return stage

    @classmethod
    async def delete_custom_stage(cls, db: AsyncSession, stage_id: str) -> bool:
        res = await db.execute(select(CompressionStage).where(CompressionStage.id == stage_id))
        stage = res.scalar_one_or_none()
        if not stage or stage.is_builtin:
            return False
        await db.delete(stage)
        await db.commit()
        return True

    @classmethod
    async def optimize_messages(
        cls,
        db: AsyncSession,
        messages: List[ChatMessage],
        model_id: str = "",
        request_headers: Optional[Dict[str, str]] = None,
        supports_vision: bool = False,
    ) -> Tuple[List[ChatMessage], Dict[str, Any]]:
        """
        Executes active compression stages on incoming messages.
        Fail-safe: returns original messages if anything fails.
        """
        headers = request_headers or {}
        # Bypass check
        if (headers.get("x-bypass-compression", "").lower() in ("true", "1") or
            headers.get("x-disable-compression", "").lower() in ("true", "1")):
            return messages, {"compressed": False, "bypass": True}

        # Global settings
        global_cfg = await cls.get_global_settings(db)
        if not global_cfg.enabled:
            return messages, {"compressed": False, "disabled": True}

        initial_tokens = count_messages_tokens(messages)
        if initial_tokens < global_cfg.trigger_token_threshold:
            return messages, {"compressed": False, "below_threshold": True, "tokens": initial_tokens}

        stages = await cls.get_stages(db)
        active_stages = [s for s in stages if s.enabled]
        if not active_stages:
            return messages, {"compressed": False, "no_active_stages": True}

        preserve_sys_prompt = should_preserve_system_prompt(
            mode=getattr(global_cfg, "preserve_system_prompt_mode", "when_caching"),
            model_id=model_id,
            request_headers=headers,
        )

        ctx = CompressionContext(
            model_id=model_id,
            supports_vision=supports_vision,
            original_tokens=initial_tokens,
            preserve_recent_turns=global_cfg.preserve_recent_turns,
            preserve_system_prompt=preserve_sys_prompt,
            request_headers=headers,
        )

        current_messages = list(messages)
        stage_breakdown = []
        t_pipeline_start = time.perf_counter()

        for stage_rec in active_stages:
            stage_impl = StageRegistry.get_stage(stage_rec.id, stage_rec)
            if not stage_impl:
                continue

            stage_before = count_messages_tokens(current_messages)
            try:
                res = await stage_impl.compress(current_messages, stage_rec.config_json, ctx)
                # Bailout check
                if res.compressed and global_cfg.min_savings_bailout_percent > 0:
                    if res.savings_percent < global_cfg.min_savings_bailout_percent:
                        # Skip advancing
                        stage_breakdown.append({
                            "stage_id": stage_rec.id,
                            "stage_name": stage_rec.name,
                            "tokens_before": stage_before,
                            "tokens_after": stage_before,
                            "savings_percent": 0.0,
                            "duration_ms": res.duration_ms,
                            "advanced": False,
                            "note": f"Skipped: savings {res.savings_percent}% < min {global_cfg.min_savings_bailout_percent}%",
                        })
                        continue

                if res.compressed:
                    if ctx.preserve_system_prompt:
                        orig_sys = [m for m in current_messages if m.role == "system"]
                        res_non_sys = [m for m in res.messages if m.role != "system"]
                        current_messages = orig_sys + res_non_sys
                    else:
                        current_messages = res.messages

                stage_breakdown.append({
                    "stage_id": stage_rec.id,
                    "stage_name": stage_rec.name,
                    "tokens_before": res.tokens_before,
                    "tokens_after": res.tokens_after,
                    "savings_percent": res.savings_percent,
                    "duration_ms": res.duration_ms,
                    "advanced": res.compressed,
                    "rules": res.rules_applied,
                })
            except Exception as e:
                logger.error(f"Compression stage {stage_rec.id} failed: {e}", exc_info=True)
                if not global_cfg.fail_open:
                    raise
                stage_breakdown.append({
                    "stage_id": stage_rec.id,
                    "stage_name": stage_rec.name,
                    "tokens_before": stage_before,
                    "tokens_after": stage_before,
                    "savings_percent": 0.0,
                    "duration_ms": 0.0,
                    "advanced": False,
                    "error": str(e),
                })

        final_tokens = count_messages_tokens(current_messages)
        total_duration = round((time.perf_counter() - t_pipeline_start) * 1000, 2)
        total_savings = max(0.0, round(((initial_tokens - final_tokens) / max(1, initial_tokens)) * 100, 2))

        summary = {
            "compressed": final_tokens < initial_tokens,
            "tokens_before": initial_tokens,
            "tokens_after": final_tokens,
            "tokens_saved": max(0, initial_tokens - final_tokens),
            "savings_percent": total_savings,
            "duration_ms": total_duration,
            "breakdown": stage_breakdown,
        }
        return current_messages, summary

    @classmethod
    async def preview_compression(
        cls,
        db: AsyncSession,
        messages: List[ChatMessage],
        stage_ids_filter: Optional[List[str]] = None,
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Playground preview without modifying live session state.
        """
        initial_tokens = count_messages_tokens(messages)
        stages = await cls.get_stages(db)
        if stage_ids_filter is not None:
            active_stages = [s for s in stages if s.id in stage_ids_filter]
        else:
            active_stages = [s for s in stages if s.enabled]

        overrides = config_overrides or {}
        ctx = CompressionContext(
            model_id="playground",
            supports_vision=False,
            original_tokens=initial_tokens,
            preserve_recent_turns=1,
        )

        current_messages = list(messages)
        step_results = []
        t0 = time.perf_counter()

        for stage_rec in active_stages:
            stage_impl = StageRegistry.get_stage(stage_rec.id, stage_rec)
            if not stage_impl:
                continue

            cfg = {**stage_rec.config_json, **overrides.get(stage_rec.id, {})}
            before_tok = count_messages_tokens(current_messages)
            res = await stage_impl.compress(current_messages, cfg, ctx)

            step_results.append({
                "stage_id": stage_rec.id,
                "stage_name": stage_rec.name,
                "icon": stage_rec.icon,
                "tokens_before": res.tokens_before,
                "tokens_after": res.tokens_after,
                "savings_percent": res.savings_percent,
                "duration_ms": res.duration_ms,
                "compressed": res.compressed,
                "rules": res.rules_applied,
            })
            if res.compressed:
                current_messages = res.messages

        final_tokens = count_messages_tokens(current_messages)
        total_duration = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "initial_tokens": initial_tokens,
            "final_tokens": final_tokens,
            "tokens_saved": max(0, initial_tokens - final_tokens),
            "savings_percent": max(0.0, round(((initial_tokens - final_tokens) / max(1, initial_tokens)) * 100, 2)),
            "duration_ms": total_duration,
            "steps": step_results,
            "compressed_messages": [m.model_dump() for m in current_messages],
        }
