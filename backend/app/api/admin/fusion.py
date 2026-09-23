from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_admin
from app.services.fusion_service import FusionService
from app.schemas.entities import FusionProfileCreate, FusionProfileUpdate, FusionProfileRead

router = APIRouter(prefix="/fusion", tags=["Admin Fusion Profiles"])

@router.get("", response_model=List[FusionProfileRead])
async def list_profiles(
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await FusionService.list_profiles(db)

@router.get("/{profile_id}", response_model=FusionProfileRead)
async def get_profile(
    profile_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    p = await FusionService.get_profile(db, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Fusion profile not found")
    return p

@router.post("", response_model=FusionProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(
    data: FusionProfileCreate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await FusionService.create_profile(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.put("/{profile_id}", response_model=FusionProfileRead)
async def update_profile(
    profile_id: int,
    data: FusionProfileUpdate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        p = await FusionService.update_profile(db, profile_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not p:
        raise HTTPException(status_code=404, detail="Fusion profile not found")
    return p

@router.delete("/{profile_id}")
async def delete_profile(
    profile_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    success = await FusionService.delete_profile(db, profile_id)
    if not success:
        raise HTTPException(status_code=404, detail="Fusion profile not found")
    return {"message": "Fusion profile deleted"}
