from pathlib import Path
import os
import shutil
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.database import PROCESSED_DIR, UPLOADS_DIR, init_db
from app.repositories import annotation_repository, media_repository, project_repository
from app.services import processing_service, reconstruction_service, report_service

ALLOWED_IMAGE_PREFIX = "image/"
ALLOWED_VIDEO_PREFIX = "video/"
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}

app = FastAPI(title="Structura AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/processed-assets", StaticFiles(directory=PROCESSED_DIR), name="processed-assets")


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    siteType: str = Field(..., min_length=1)
    description: str = ""


class AnnotationCreate(BaseModel):
    text: str = Field(..., min_length=1)


class ProcessingOptions(BaseModel):
    extractionFpsMode: str = "Balanced"


class SparseReconstructionOptions(BaseModel):
    matchingMode: str = "Auto"


def _is_dev_mode() -> bool:
    return os.getenv("STRUCTURA_ENV", "development").lower() in {"local", "dev", "development", "test"}


def _remove_project_storage(project_id: str) -> None:
    for root in (UPLOADS_DIR, PROCESSED_DIR):
        target = root / project_id
        if target.exists():
            resolved_root = root.resolve()
            resolved_target = target.resolve()
            if resolved_root not in resolved_target.parents:
                raise HTTPException(status_code=500, detail="Refusing unsafe storage cleanup path")
            shutil.rmtree(resolved_target)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "product": "Structura AI"}


@app.get("/diagnostics")
def diagnostics() -> dict:
    colmap = reconstruction_service.diagnostics()
    return {
        "product": "Structura AI",
        "colmapAvailable": colmap["colmapAvailable"],
        "colmapVersion": colmap["colmapVersion"],
        "colmapPath": colmap["colmapPath"],
        "colmapCudaHint": colmap["colmapCudaHint"],
        "denseReconstructionLikelyAvailable": colmap["denseReconstructionLikelyAvailable"],
        "colmap": colmap,
    }


@app.get("/projects")
def list_projects() -> list[dict]:
    return project_repository.list_projects()


@app.post("/projects")
def create_project(payload: ProjectCreate) -> dict:
    project = project_repository.create_project(
        name=payload.name.strip(),
        site_type=payload.siteType.strip(),
        description=payload.description.strip(),
    )
    annotation_repository.seed_default_annotations(project["id"])
    return project


@app.get("/projects/{project_id}")
def get_project(project_id: str) -> dict:
    project = project_repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    media = media_repository.list_media(project_id)
    return {**project, "media": media, "mediaCount": len(media)}


@app.post("/projects/{project_id}/media")
async def upload_media(project_id: str, files: list[UploadFile] = File(...)) -> dict:
    project = project_repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one image or one video")

    existing_video_count = media_repository.count_video(project_id)
    staged: list[tuple[UploadFile, str]] = []
    new_video_count = 0

    for file in files:
        content_type = file.content_type or ""
        if content_type.startswith(ALLOWED_IMAGE_PREFIX):
            staged.append((file, "image"))
        elif content_type.startswith(ALLOWED_VIDEO_PREFIX):
            suffix = Path(file.filename or "").suffix.lower()
            if suffix not in ALLOWED_VIDEO_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail="Video uploads must be .mp4, .mov, or .webm for frame extraction.",
                )
            new_video_count += 1
            staged.append((file, "video"))
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported media type for {file.filename}. Upload images or one video.",
            )

    if existing_video_count + new_video_count > 1:
        raise HTTPException(status_code=400, detail="Only one video can be uploaded per project")

    project_dir = UPLOADS_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for file, media_type in staged:
        suffix = Path(file.filename or "").suffix
        stored_name = f"{uuid4()}{suffix}"
        target_path = project_dir / stored_name
        content = await file.read()
        target_path.write_bytes(content)
        saved.append(
            media_repository.add_media(
                project_id=project_id,
                filename=stored_name,
                original_filename=file.filename or stored_name,
                content_type=file.content_type or "application/octet-stream",
                media_type=media_type,
                size_bytes=len(content),
            )
        )

    project_repository.set_media_uploaded(project_id)
    return {"uploaded": saved, "count": len(saved)}


@app.post("/projects/{project_id}/process")
def start_processing(project_id: str, payload: ProcessingOptions | None = None) -> dict:
    if not project_repository.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        status = processing_service.start_processing(project_id, payload.extractionFpsMode if payload else "Balanced")
    except processing_service.ProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not status:
        raise HTTPException(status_code=404, detail="Project not found")
    return status


@app.get("/projects/{project_id}/status")
def get_status(project_id: str) -> dict:
    status = processing_service.get_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="Project not found")
    return status


@app.get("/projects/{project_id}/frames")
def list_frames(project_id: str) -> list[dict[str, str]]:
    if not project_repository.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return processing_service.list_frames(project_id)


@app.get("/projects/{project_id}/capture-summary")
def get_capture_summary(project_id: str) -> dict:
    summary = processing_service.capture_summary(project_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Project not found")
    return summary


@app.post("/projects/{project_id}/reconstruct/sparse")
def run_sparse_reconstruction(project_id: str, payload: SparseReconstructionOptions | None = None) -> dict:
    if not project_repository.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return reconstruction_service.run_sparse_reconstruction(project_id, payload.matchingMode if payload else "Auto")
    except reconstruction_service.ReconstructionError as exc:
        summary = reconstruction_service.reconstruction_summary(project_id)
        raise HTTPException(status_code=400, detail={"message": str(exc), "summary": summary}) from exc


@app.post("/projects/{project_id}/reconstruct/dense")
def run_dense_reconstruction(project_id: str) -> dict:
    if not project_repository.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return reconstruction_service.run_dense_reconstruction(project_id)
    except reconstruction_service.ReconstructionError as exc:
        summary = reconstruction_service.reconstruction_summary(project_id)
        raise HTTPException(status_code=400, detail={"message": str(exc), "summary": summary}) from exc


@app.get("/projects/{project_id}/reconstruction-summary")
def get_reconstruction_summary(project_id: str) -> dict:
    summary = reconstruction_service.reconstruction_summary(project_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Project not found")
    return summary


@app.get("/projects/{project_id}/point-cloud")
def get_point_cloud(project_id: str, max_points: int = 50000) -> dict:
    point_cloud = reconstruction_service.point_cloud(project_id, max_points=max_points)
    if point_cloud is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return point_cloud


@app.get("/projects/{project_id}/dense-point-cloud")
def get_dense_point_cloud(project_id: str, max_points: int = 100000) -> dict:
    point_cloud = reconstruction_service.dense_point_cloud(project_id, max_points=max_points)
    if point_cloud is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return point_cloud


@app.get("/projects/{project_id}/scene-analysis")
def get_scene_analysis(project_id: str) -> dict:
    analysis = reconstruction_service.scene_analysis(project_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return analysis


@app.delete("/projects/{project_id}")
def delete_project(project_id: str) -> dict[str, str]:
    if not project_repository.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    project_repository.delete_project(project_id)
    _remove_project_storage(project_id)
    return {"status": "deleted", "projectId": project_id}


@app.post("/dev/reset")
def reset_dev_data() -> dict[str, str]:
    if not _is_dev_mode():
        raise HTTPException(status_code=403, detail="Local development reset is disabled outside dev mode")

    project_repository.reset_all_projects()
    for root in (UPLOADS_DIR, PROCESSED_DIR):
        root.mkdir(parents=True, exist_ok=True)
        for item in root.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            elif item.is_file():
                item.unlink()
    return {"status": "reset"}


@app.get("/projects/{project_id}/model")
def get_model(project_id: str) -> dict[str, str]:
    project = project_repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["status"] != "Ready":
        raise HTTPException(status_code=409, detail="Digital twin model is not ready yet")
    return {"modelUrl": "/models/sample-condo.glb"}


@app.get("/projects/{project_id}/report")
def get_report(project_id: str) -> dict:
    report = report_service.build_report(project_id)
    if not report:
        raise HTTPException(status_code=404, detail="Project not found")
    return report


@app.get("/projects/{project_id}/annotations")
def list_annotations(project_id: str) -> list[dict]:
    if not project_repository.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return annotation_repository.list_annotations(project_id)


@app.post("/projects/{project_id}/annotations")
def add_annotation(project_id: str, payload: AnnotationCreate) -> dict:
    if not project_repository.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return annotation_repository.add_annotation(project_id, payload.text)
