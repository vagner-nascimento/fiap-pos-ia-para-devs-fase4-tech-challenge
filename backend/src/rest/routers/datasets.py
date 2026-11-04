"""Endpoints de disponibilidade, download e catálogo de datasets."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from models.rest.session import DatasetStatusResponse, ReferenceClipInfo
from services.dataset_service import DatasetService

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.get("/fisio/status", response_model=DatasetStatusResponse)
def dataset_status() -> DatasetStatusResponse:
    return DatasetStatusResponse(**DatasetService().status())


@router.post("/fisio/download", response_model=DatasetStatusResponse, status_code=status.HTTP_202_ACCEPTED)
def download_dataset(background_tasks: BackgroundTasks) -> DatasetStatusResponse:
    service = DatasetService()
    current = service.status()
    if current["status"] == "ready":
        return DatasetStatusResponse(**current)
    requested = service.request_download()
    background_tasks.add_task(service.download)
    return DatasetStatusResponse(**requested)


@router.get("/fisio/clips", response_model=list[ReferenceClipInfo])
def dataset_clips() -> list[ReferenceClipInfo]:
    clips = DatasetService().list_clips()
    if not clips:
        raise HTTPException(status_code=404, detail="Dataset ainda não foi baixado.")
    return clips
