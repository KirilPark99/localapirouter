from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_admin
from app.services.routing_service import RoutingService
from app.schemas.entities import RoutingProfileCreate, RoutingProfileUpdate, RoutingProfileRead

router = APIRouter(prefix="/routes", tags=["Admin Routing Profiles"])

@router.get("", response_model=List[RoutingProfileRead])
async def list_profiles(
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await RoutingService.list_profiles(db)

@router.get("/{profile_id}", response_model=RoutingProfileRead)
async def get_profile(
    profile_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    p = await RoutingService.get_profile(db, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Routing profile not found")
    return p

@router.post("", response_model=RoutingProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(
    data: RoutingProfileCreate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await RoutingService.create_profile(db, data)

@router.put("/{profile_id}", response_model=RoutingProfileRead)
async def update_profile(
    profile_id: int,
    data: RoutingProfileUpdate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    p = await RoutingService.update_profile(db, profile_id, data)
    if not p:
        raise HTTPException(status_code=404, detail="Routing profile not found")
    return p

@router.delete("/{profile_id}")
async def delete_profile(
    profile_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    success = await RoutingService.delete_profile(db, profile_id)
    if not success:
        raise HTTPException(status_code=404, detail="Routing profile not found")
    return {"message": "Routing profile deleted"}
