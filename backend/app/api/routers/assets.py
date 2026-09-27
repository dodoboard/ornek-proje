from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from app.api.deps import SessionDep, SettingsDep, StorageDep
from app.core.errors import FileTooLargeError, NotFoundError
from app.schemas.asset import AssetRead
from app.services import assets as service

router = APIRouter(prefix="/assets", tags=["assets"])

MULTIPART_OVERHEAD_BYTES = 64 * 1024


@router.post("", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    request: Request,
    file: Annotated[UploadFile, File(description="JPEG, PNG, WEBP, MP4, MOV, WAV, MP3 or M4A")],
    session: SessionDep,
    settings: SettingsDep,
    storage: StorageDep,
) -> AssetRead:
    declared = request.headers.get("content-length")
    limit = service.max_upload_bytes(settings) + MULTIPART_OVERHEAD_BYTES
    if declared and declared.isdigit() and int(declared) > limit:
        raise FileTooLargeError()
    asset = await run_in_threadpool(
        service.ingest_upload, session, settings, storage, file.file, file.filename
    )
    return AssetRead.model_validate(asset)


@router.get("/{asset_id}", response_model=AssetRead)
def get_asset(asset_id: str, session: SessionDep) -> AssetRead:
    return AssetRead.model_validate(service.get_asset(session, asset_id))


@router.get("/{asset_id}/content", response_class=FileResponse)
def get_asset_content(asset_id: str, session: SessionDep, storage: StorageDep) -> FileResponse:
    asset = service.get_asset(session, asset_id)
    path = storage.resolve(asset.path)
    if not path.is_file():
        raise NotFoundError("Asset file is missing from storage.")
    return FileResponse(
        path,
        media_type=asset.mime,
        filename=path.name,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"},
    )


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: str, session: SessionDep, storage: StorageDep) -> None:
    service.delete_asset(session, storage, asset_id)
