from typing import Dict, List, Optional, Type
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import CompressionStage, CompressionGlobalSetting
from app.compression.base import BaseCompressionStage
from app.compression.stages import BUILTIN_STAGES
from app.compression.stages.custom_regex import CustomRegexStage

class StageRegistry:
    _stages: Dict[str, Type[BaseCompressionStage]] = {}
    _instances: Dict[str, BaseCompressionStage] = {}

    @classmethod
    def register(cls, stage_cls: Type[BaseCompressionStage]) -> None:
        cls._stages[stage_cls.id] = stage_cls
        cls._instances[stage_cls.id] = stage_cls()

    @classmethod
    def get_stage(cls, stage_id: str, stage_record: Optional[CompressionStage] = None) -> Optional[BaseCompressionStage]:
        if stage_id in cls._instances:
            return cls._instances[stage_id]

        if stage_record and stage_record.stage_type == "custom_regex":
            # Instantiate custom regex stage instance
            inst = CustomRegexStage()
            inst.id = stage_record.id
            inst.name = stage_record.name
            inst.description = stage_record.description
            inst.icon = stage_record.icon
            inst.is_builtin = False
            return inst

        return None

    @classmethod
    def list_stage_classes(cls) -> List[Type[BaseCompressionStage]]:
        return list(cls._stages.values())

    @classmethod
    async def sync_with_db(cls, db: AsyncSession) -> None:
        """
        Synchronize registered built-in stages and default global settings with database.
        Inserts new stages if not present without overwriting user customizations.
        """
        # 1. Global Settings
        g_res = await db.execute(select(CompressionGlobalSetting).limit(1))
        global_setting = g_res.scalar_one_or_none()
        if not global_setting:
            new_global = CompressionGlobalSetting(
                enabled=True,
                trigger_token_threshold=1000,
                min_savings_bailout_percent=0.0,
                preserve_recent_turns=1,
                enable_telemetry=True,
                fail_open=True,
            )
            db.add(new_global)

        # 2. Builtin Stages
        existing_res = await db.execute(select(CompressionStage))
        existing_map = {s.id: s for s in existing_res.scalars().all()}

        for stage_cls in BUILTIN_STAGES:
            st = stage_cls()
            if st.id not in existing_map:
                default_config = {f.key: f.default_value for f in st.get_config_schema()}
                new_stage = CompressionStage(
                    id=st.id,
                    name=st.name,
                    description=st.description,
                    icon=st.icon,
                    stage_type=st.stage_type,
                    priority_order=st.default_order,
                    enabled=st.default_enabled,
                    is_builtin=True,
                    config_json=default_config,
                )
                db.add(new_stage)

        await db.commit()

# Register builtins immediately
for _cls in BUILTIN_STAGES:
    StageRegistry.register(_cls)
