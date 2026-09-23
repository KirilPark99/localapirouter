from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_admin
from app.services.model_discovery_service import ModelDiscoveryService
from app.services.model_ratings_service import ModelRatingsService
from app.services.model_limits_service import ModelLimitsService
from app.schemas.entities import DiscoveredModelRead, DiscoveredModelUpdate, ModelLimitsRead
from app.core.errors import RouterException

router = APIRouter(prefix="/models", tags=["Admin Models"])

@router.get("", response_model=List[DiscoveredModelRead])
async def list_models(
    provider_id: Optional[int] = None,
    credential_id: Optional[int] = None,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await ModelDiscoveryService.list_models(db, provider_id=provider_id, credential_id=credential_id)

@router.post("/fetch/{credential_id}", response_model=List[DiscoveredModelRead])
async def fetch_models_for_credential(
    credential_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await ModelDiscoveryService.fetch_models_for_credential(db, credential_id)
    except RouterException as re:
        raise HTTPException(status_code=re.status_code, detail=re.message)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/fetch-all")
async def fetch_all_models(
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await ModelDiscoveryService.fetch_all_models(db)

@router.post("/fetch-provider/{provider_id}")
async def fetch_models_for_provider(
    provider_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await ModelDiscoveryService.fetch_models_for_provider(db, provider_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/sync-ratings")
async def sync_model_ratings(
    username: str = Depends(get_current_admin),
):
    try:
        return ModelRatingsService.sync_from_web()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-update")
async def batch_update_models(
    payload: dict,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    model_ids = payload.get("model_ids", [])
    enabled = payload.get("enabled")
    is_visible = payload.get("is_visible")
    context_length = payload.get("context_length")
    set_reasoning_effort = "reasoning_effort" in payload
    reasoning_effort = payload.get("reasoning_effort")
    set_temperature = "temperature" in payload
    temperature = payload.get("temperature")
    try:
        updated_count = await ModelDiscoveryService.batch_update_models(
            db,
            model_ids,
            enabled=enabled,
            is_visible=is_visible,
            context_length=context_length,
            reasoning_effort=reasoning_effort,
            set_reasoning_effort=set_reasoning_effort,
            temperature=temperature,
            set_temperature=set_temperature,
        )
        return {"updated_count": updated_count}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.post("/set-visible-only")
async def set_visible_only(
    payload: dict,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    model_ids = payload.get("model_ids", [])
    visible_count = await ModelDiscoveryService.set_visible_only(db, model_ids)
    return {"visible_count": visible_count}

@router.post("/visibility-all")
async def set_all_visibility(
    payload: dict,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    is_visible = payload.get("is_visible", True)
    provider_id = payload.get("provider_id")
    count = await ModelDiscoveryService.set_all_visibility(db, is_visible=is_visible, provider_id=provider_id)
    return {"updated_count": count}

@router.post("/manual", response_model=DiscoveredModelRead, status_code=status.HTTP_201_CREATED)
async def add_model_manually(
    payload: dict,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    provider_id = payload.get("provider_id")
    provider_model_id = payload.get("provider_model_id")
    display_name = payload.get("display_name", "")
    credential_id = payload.get("credential_id")
    context_length = payload.get("context_length")
    max_output = payload.get("max_output_tokens")

    if not provider_id or not provider_model_id:
        raise HTTPException(status_code=400, detail="provider_id and provider_model_id are required")

    return await ModelDiscoveryService.add_model_manually(
        db=db,
        provider_id=provider_id,
        credential_id=credential_id,
        provider_model_id=provider_model_id,
        display_name=display_name,
        context_length=context_length,
        max_output_tokens=max_output,
    )

@router.put("/{model_id}", response_model=DiscoveredModelRead)
async def update_model(
    model_id: int,
    data: DiscoveredModelUpdate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        updated = await ModelDiscoveryService.update_model(db, model_id, data)
        if not updated:
            raise HTTPException(status_code=404, detail="Model not found")
        return updated
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.delete("/{model_id}")
async def delete_model(
    model_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    success = await ModelDiscoveryService.delete_model(db, model_id)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"message": "Model deleted"}

@router.get("/{model_id}/limits", response_model=ModelLimitsRead)
async def get_model_limits(
    model_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await ModelLimitsService.get_model_limits(db, model_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
