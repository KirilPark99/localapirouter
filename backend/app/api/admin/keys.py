from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_admin
from app.services.api_key_service import ApiKeyService
from app.schemas.entities import RouterApiKeyCreate, RouterApiKeyUpdate, RouterApiKeyRead, RouterApiKeyCreated, NotesUpdate

router = APIRouter(prefix="/keys", tags=["Admin Router API Keys"])

@router.get("", response_model=List[RouterApiKeyRead])
async def list_keys(
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await ApiKeyService.list_keys(db)

@router.post("", response_model=RouterApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_key(
    data: RouterApiKeyCreate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await ApiKeyService.create_key(db, data)

@router.put("/{key_id}", response_model=RouterApiKeyRead)
async def update_key(
    key_id: int,
    data: RouterApiKeyUpdate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    updated = await ApiKeyService.update_key(db, key_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Key not found")
    return updated

@router.get("/{key_id}/usage")
async def key_quota_usage(key_id: int, username: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from app.services.quota_service import QuotaService
    key = await ApiKeyService.get_key(db, key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="Key not found")
    return await QuotaService.usage(db, key)

@router.put("/{key_id}/notes")
async def update_key_notes(
    key_id: int,
    data: NotesUpdate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    notes = await ApiKeyService.update_key_notes(db, key_id, data.notes)
    if notes is None and not await ApiKeyService.get_key(db, key_id):
        raise HTTPException(status_code=404, detail="Key not found")
    return {"message": "Notes updated", "notes": notes}

@router.delete("/{key_id}")
async def delete_key(
    key_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    success = await ApiKeyService.delete_key(db, key_id)
    if not success:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"message": "API key deleted"}
