from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_admin
from app.compression.pipeline import CompressionPipelineService
from app.compression.registry import StageRegistry
from app.schemas.chat import ChatMessage

router = APIRouter(prefix="/compression", tags=["Admin Compression"])

class GlobalSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    trigger_token_threshold: Optional[int] = None
    min_savings_bailout_percent: Optional[float] = None
    preserve_recent_turns: Optional[int] = None
    preserve_system_prompt_mode: Optional[str] = None
    enable_telemetry: Optional[bool] = None
    fail_open: Optional[bool] = None

class StageUpdate(BaseModel):
    enabled: Optional[bool] = None
    priority_order: Optional[int] = None
    config_json: Optional[Dict[str, Any]] = None
    name: Optional[str] = None
    description: Optional[str] = None
    custom_rules: Optional[List[Dict[str, Any]]] = None

class StagesReorderRequest(BaseModel):
    ordered_ids: List[str]

class CustomStageCreate(BaseModel):
    id: Optional[str] = None
    name: str
    description: str = ""
    icon: str = "Sliders"
    priority_order: int = 50
    guard_code_blocks: bool = True
    rules: List[Dict[str, Any]] = Field(default_factory=list)

class PreviewRequest(BaseModel):
    messages: List[ChatMessage]
    stage_ids: Optional[List[str]] = None
    config_overrides: Optional[Dict[str, Any]] = None

@router.get("/settings")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    settings = await CompressionPipelineService.get_global_settings(db)
    return {
        "enabled": settings.enabled,
        "trigger_token_threshold": settings.trigger_token_threshold,
        "min_savings_bailout_percent": settings.min_savings_bailout_percent,
        "preserve_recent_turns": settings.preserve_recent_turns,
        "preserve_system_prompt_mode": getattr(settings, "preserve_system_prompt_mode", "when_caching"),
        "enable_telemetry": settings.enable_telemetry,
        "fail_open": settings.fail_open,
    }

@router.put("/settings")
async def update_settings(
    payload: GlobalSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    update_data = payload.model_dump(exclude_unset=True)
    settings = await CompressionPipelineService.update_global_settings(db, update_data)
    return {
        "message": "Global compression settings updated",
        "settings": {
            "enabled": settings.enabled,
            "trigger_token_threshold": settings.trigger_token_threshold,
            "min_savings_bailout_percent": settings.min_savings_bailout_percent,
            "preserve_recent_turns": settings.preserve_recent_turns,
            "preserve_system_prompt_mode": getattr(settings, "preserve_system_prompt_mode", "when_caching"),
            "enable_telemetry": settings.enable_telemetry,
            "fail_open": settings.fail_open,
        },
    }

@router.get("/stages")
async def get_stages(
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    stages = await CompressionPipelineService.get_stages(db)
    result = []
    for s in stages:
        stage_impl = StageRegistry.get_stage(s.id, s)
        schema = stage_impl.get_config_schema() if stage_impl else []
        result.append({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "icon": s.icon,
            "stage_type": s.stage_type,
            "priority_order": s.priority_order,
            "enabled": s.enabled,
            "is_builtin": s.is_builtin,
            "config_json": s.config_json,
            "custom_rules": s.custom_rules,
            "config_schema": [f.model_dump() for f in schema],
        })
    return result

@router.put("/stages/reorder")
async def reorder_stages(
    payload: StagesReorderRequest,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    stages = await CompressionPipelineService.reorder_stages(db, payload.ordered_ids)
    return {"message": "Stages reordered", "count": len(stages)}

@router.put("/stages/{stage_id}")
async def update_stage(
    stage_id: str,
    payload: StageUpdate,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    update_data = payload.model_dump(exclude_unset=True)
    stage = await CompressionPipelineService.update_stage(db, stage_id, update_data)
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    return {"message": f"Stage {stage_id} updated", "stage": stage.id}

@router.post("/stages", status_code=status.HTTP_201_CREATED)
async def create_custom_stage(
    payload: CustomStageCreate,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    data = payload.model_dump()
    stage = await CompressionPipelineService.create_custom_stage(db, data)
    return {"message": "Custom stage created", "stage_id": stage.id}

@router.delete("/stages/{stage_id}")
async def delete_stage(
    stage_id: str,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    deleted = await CompressionPipelineService.delete_custom_stage(db, stage_id)
    if not deleted:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete stage (not found or built-in stages cannot be deleted, only disabled)",
        )
    return {"message": f"Stage {stage_id} deleted"}

@router.post("/preview")
async def preview_compression(
    payload: PreviewRequest,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    preview_data = await CompressionPipelineService.preview_compression(
        db=db,
        messages=payload.messages,
        stage_ids_filter=payload.stage_ids,
        config_overrides=payload.config_overrides,
    )
    return preview_data
