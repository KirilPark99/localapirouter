from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_admin
from app.services.judge_service import JudgeService
from app.schemas.entities import (
    JudgeProfileCreate,
    JudgeProfileUpdate,
    JudgeProfileRead,
    JudgeTestRequest,
    JudgeTestResponse,
)

router = APIRouter(prefix="/judges", tags=["Admin Judge Profiles"])

@router.get("", response_model=List[JudgeProfileRead])
async def list_profiles(
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await JudgeService.list_profiles(db)

@router.get("/{profile_id}", response_model=JudgeProfileRead)
async def get_profile(
    profile_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    p = await JudgeService.get_profile(db, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Judge profile not found")
    return p

@router.post("", response_model=JudgeProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(
    data: JudgeProfileCreate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await JudgeService.create_profile(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.put("/{profile_id}", response_model=JudgeProfileRead)
async def update_profile(
    profile_id: int,
    data: JudgeProfileUpdate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        p = await JudgeService.update_profile(db, profile_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not p:
        raise HTTPException(status_code=404, detail="Judge profile not found")
    return p

@router.delete("/{profile_id}")
async def delete_profile(
    profile_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    success = await JudgeService.delete_profile(db, profile_id)
    if not success:
        raise HTTPException(status_code=404, detail="Judge profile not found")
    return {"message": "Judge profile deleted"}

@router.post("/{profile_id}/test", response_model=JudgeTestResponse)
async def test_judge_evaluation(
    profile_id: int,
    payload: JudgeTestRequest,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await JudgeService.test_judge_evaluation(db, profile_id, payload.prompt)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
