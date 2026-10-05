import time
import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import CompressionStage, CompressionGlobalSetting
from app.schemas.chat import ChatMessage
from app.compression.base import CompressionContext, StageExecutionResult
from app.compression.registry import StageRegistry
from app.compression.tokenizer import count_messages_tokens
from app.compression.safety import execute_stage
from app.compression.validation import validate_stage_config, validate_globals

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
        validate_globals(data)
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

        impl = StageRegistry.get_stage(stage_id, stage)
        if "config_json" in data:
            await asyncio.to_thread(validate_stage_config, impl, data["config_json"])
        if "custom_rules" in data:
            await asyncio.to_thread(validate_stage_config, impl, {"rules": data["custom_rules"]})
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
            stage.config_json = {**(stage.config_json or {}), "rules": data["custom_rules"]}

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

        from app.compression.stages.custom_regex import CustomRegexStage
        await asyncio.to_thread(validate_stage_config, CustomRegexStage(), config_json)
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
        supports_vision: Optional[bool] = None,
        provider_name: Optional[str] = None,
        stage_ids_filter: Optional[List[str]] = None,
        config_overrides: Optional[Dict[str, Any]] = None,
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
        active_stages = [s for s in stages if s.enabled and (stage_ids_filter is None or s.id in stage_ids_filter)]
        if not active_stages:
            return messages, {"compressed": False, "no_active_stages": True}

        preserve_sys_prompt = should_preserve_system_prompt(
            mode=getattr(global_cfg, "preserve_system_prompt_mode", "when_caching"),
            model_id=model_id,
            provider_name=provider_name,
            request_headers=headers,
        )

        ctx = CompressionContext(
            model_id=model_id,
            supports_vision=supports_vision,
            original_tokens=initial_tokens,
            preserve_recent_turns=global_cfg.preserve_recent_turns,
            preserve_system_prompt=preserve_sys_prompt,
            request_headers=headers,
            metadata={"latest_user_query": next((m.content for m in reversed(messages) if m.role == "user" and isinstance(m.content, str)), "")},
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
                cfg = {**(stage_rec.config_json or {}), **((config_overrides or {}).get(stage_rec.id, {}))}
                await asyncio.to_thread(validate_stage_config, stage_impl, cfg)
                res = await execute_stage(stage_impl, current_messages, cfg, ctx)
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
                    "warning": res.warning,
                    "icon": stage_rec.icon,
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
            "token_count_is_estimate": True,
            "enable_telemetry": getattr(global_cfg, "enable_telemetry", True),
        }
        return current_messages, summary

    @classmethod
    async def preview_compression(
        cls, db: AsyncSession, messages: List[ChatMessage],
        stage_ids_filter: Optional[List[str]] = None,
        config_overrides: Optional[Dict[str, Any]] = None,
        model_id: str = "", supports_vision: Optional[bool] = None,
        provider_name: Optional[str] = None,
        request_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        if config_overrides is not None:
            stages = {s.id: s for s in await cls.get_stages(db)}
            for stage_id, override in config_overrides.items():
                if stage_id not in stages or not isinstance(override, dict):
                    raise ValueError("Invalid preview override")
                record = stages[stage_id]
                await asyncio.to_thread(validate_stage_config, StageRegistry.get_stage(stage_id, record),
                                        {**(record.config_json or {}), **override})
        output, summary = await cls.optimize_messages(
            db, messages, model_id=model_id, supports_vision=supports_vision,
            provider_name=provider_name, request_headers=request_headers,
            stage_ids_filter=stage_ids_filter, config_overrides=config_overrides,
        )
        initial = count_messages_tokens(messages)
        final = count_messages_tokens(output)
        return {
            "initial_tokens": initial, "final_tokens": final,
            "tokens_saved": max(0, initial-final),
            "savings_percent": summary.get("savings_percent", 0),
            "duration_ms": summary.get("duration_ms", 0),
            "steps": [{**step, "compressed": step.get("advanced", False)}
                      for step in summary.get("breakdown", [])],
            "compressed_messages": [m.model_dump() for m in output],
            "token_count_is_estimate": True,
            "policy": summary,
        }
