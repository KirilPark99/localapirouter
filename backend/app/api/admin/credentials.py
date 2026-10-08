from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_admin
from app.services.credential_service import CredentialService
from app.schemas.entities import CredentialCreate, CredentialUpdate, CredentialRead, CredentialTestResult, CredentialBulkAssignProxy, CredentialBulkAssignGroup, NotesUpdate

from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from app.modules.base import SubscriptionLimits, SubscriptionResetResult

router = APIRouter(prefix="/credentials", tags=["Admin Credentials"])

@router.get("/{credential_id}/subscription-limits", response_model=SubscriptionLimits)
async def subscription_limits(credential_id: int, username: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await CredentialService.get_subscription_limits(db, credential_id)
    if result is None:
        raise HTTPException(404, "Credential not found")
    return result

class SubscriptionResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    redeem_request_id: UUID
    confirmed: bool = Field(strict=True)


@router.post("/{credential_id}/subscription-limits/reset", response_model=SubscriptionResetResult)
async def reset_subscription_limits(credential_id: int, data: SubscriptionResetRequest,
                                    username: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    if not data.confirmed:
        raise HTTPException(400, "Explicit confirmation is required to spend a Codex reset")
    result = await CredentialService.reset_subscription_limits(db, credential_id, str(data.redeem_request_id))
    if result is None:
        raise HTTPException(404, "Credential not found")
    return result


@router.get("/{credential_id}/usage", response_model=List[dict])
async def credential_usage(credential_id: int, username: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from app.services.quota_service import QuotaService
    credential = await CredentialService.get_credential(db, credential_id)
    if credential is None:
        raise HTTPException(404, "Credential not found")
    return await QuotaService.usage(db, credential)


@router.get("", response_model=List[CredentialRead])
async def list_credentials(
    provider_id: Optional[int] = None,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await CredentialService.list_credentials(db, provider_id=provider_id)

@router.post("/bulk-assign-proxy", response_model=List[CredentialRead])
async def bulk_assign_proxy(
    data: CredentialBulkAssignProxy,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await CredentialService.bulk_assign_proxy(db, data.credential_ids, data.proxy_id)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.post("/bulk-assign-group", response_model=List[CredentialRead])
async def bulk_assign_group(
    data: CredentialBulkAssignGroup,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await CredentialService.bulk_assign_group(db, data.credential_ids, data.group_name)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.post("", response_model=CredentialRead, status_code=status.HTTP_201_CREATED)
async def create_credential(
    data: CredentialCreate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await CredentialService.create_credential(db, data)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.put("/{credential_id}", response_model=CredentialRead)
async def update_credential(
    credential_id: int,
    data: CredentialUpdate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        updated = await CredentialService.update_credential(db, credential_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="Credential not found")
    return updated

@router.delete("/{credential_id}")
async def delete_credential(
    credential_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    success = await CredentialService.delete_credential(db, credential_id)
    if not success:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"message": "Credential deleted"}

@router.post("/{credential_id}/test", response_model=CredentialTestResult)
async def test_credential(
    credential_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await CredentialService.test_credential(db, credential_id)

@router.post("/{credential_id}/reset-circuit-breaker")
async def reset_circuit_breaker(
    credential_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    await CredentialService.reset_circuit_breaker(db, credential_id)
    return {"message": "Circuit breaker reset to HEALTHY"}

@router.post("/{credential_id}/preferences")
async def set_model_preferences(
    credential_id: int,
    payload: dict,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    model_ids = payload.get("model_ids", [])
    await CredentialService.set_model_preferences(db, credential_id, model_ids)
    return {"message": "Model preferences saved"}

@router.put("/{credential_id}/notes")
async def update_credential_notes(
    credential_id: int,
    data: NotesUpdate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    notes = await CredentialService.update_credential_notes(db, credential_id, data.notes)
    if notes is None and not await CredentialService.get_credential(db, credential_id):
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"message": "Notes updated", "notes": notes}
