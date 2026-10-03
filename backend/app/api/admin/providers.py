from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_admin
from app.services.provider_service import ProviderService
from app.schemas.entities import ProviderCreate, ProviderUpdate, ProviderRead, NotesUpdate

router = APIRouter(prefix="/providers", tags=["Admin Providers"])

@router.get("", response_model=List[ProviderRead])
async def list_providers(
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await ProviderService.list_providers(db)

@router.get("/{provider_id}", response_model=ProviderRead)
async def get_provider(
    provider_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    p = await ProviderService.get_provider(db, provider_id)
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    return p

@router.post("", response_model=ProviderRead, status_code=status.HTTP_201_CREATED)
async def create_provider(
    data: ProviderCreate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await ProviderService.create_provider(db, data)

@router.put("/{provider_id}", response_model=ProviderRead)
async def update_provider(
    provider_id: int,
    data: ProviderUpdate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    p = await ProviderService.update_provider(db, provider_id, data)
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    return p

@router.put("/{provider_id}/notes")
async def update_provider_notes(
    provider_id: int,
    data: NotesUpdate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    p = await ProviderService.get_provider(db, provider_id)
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    notes = await ProviderService.update_provider_notes(db, provider_id, data.notes)
    return {"id": provider_id, "notes": notes}

@router.delete("/{provider_id}")
async def delete_provider(
    provider_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    success = await ProviderService.delete_provider(db, provider_id)
    if not success:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"message": "Provider deleted"}
