from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_admin
from app.services.backup_service import BackupService

router = APIRouter(prefix="/backup", tags=["Admin Backup & Migration"])


class ExportRequest(BaseModel):
    provider_ids: Optional[List[int]] = None
    include_proxies: bool = True
    passphrase: str = Field(min_length=12)


class PreviewRequest(BaseModel):
    raw_payload: Dict[str, Any]
    passphrase: str = Field(min_length=12)


class ImportRequest(BaseModel):
    raw_payload: Dict[str, Any]
    passphrase: str = Field(min_length=12)
    update_existing_providers: bool = True
    skip_duplicate_credentials: bool = True
    auto_discover_models: bool = True


@router.post("/export")
async def export_backup(
    data: ExportRequest,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Exports providers, credentials (with decrypted keys), and optionally proxies
    into a portable JSON backup structure, optionally encrypted with passphrase.
    """
    try:
        return await BackupService.export_data(
            db=db,
            provider_ids=data.provider_ids,
            include_proxies=data.include_proxies,
            passphrase=data.passphrase,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Configuration export error: {str(e)}")


@router.post("/preview")
async def preview_backup(
    data: PreviewRequest,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Validates backup payload and returns summary of what will be imported/updated.
    """
    try:
        return await BackupService.preview_import(
            db=db,
            raw_payload=data.raw_payload,
            passphrase=data.passphrase,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup parse error: {str(e)}")


@router.post("/import")
async def import_backup(
    data: ImportRequest,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Imports providers and credentials into this server, re-encrypting secrets with this server's master key.
    """
    try:
        return await BackupService.import_data(
            db=db,
            raw_payload=data.raw_payload,
            passphrase=data.passphrase,
            update_existing_providers=data.update_existing_providers,
            skip_duplicate_credentials=data.skip_duplicate_credentials,
            auto_discover_models=data.auto_discover_models,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data import error: {str(e)}")
