from pathlib import Path
import os
import shutil
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.database import PROCESSED_DIR, UPLOADS_DIR, init_db
from app.repositories import annotation_repository, capture_repository, media_repository, model_artifact_repository, photogrammetry_job_repository, project_repository
from app.services import comparison_analysis_service, job_progress_service, model_artifact_service, processing_service, realityscan_service, reconstruction_service, report_service, visual_preview_service

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
    matchingMode: str | None = None
    frameSelectionMode: str | None = None


class FrameSelectionPreviewOptions(BaseModel):
    mode: str = "Balanced subset"


class ViewerTransformPayload(BaseModel):
    rotationX: float = 0
    rotationY: float = 0
    rotationZ: float = 0
    flipX: bool = False
    flipY: bool = False
    flipZ: bool = False
    scale: float = 1
    offsetX: float = 0
    offsetY: float = 0
    offsetZ: float = 0
    previewMode: str = "auto"


class VisualPreviewTrainPayload(BaseModel):
    visualPreviewId: str | None = None
    attemptId: str | None = None
    maxIterations: int | None = Field(default=None, ge=1, le=100000)
    trainingPreset: str | None = None
    preset: str | None = None


class VisualPreviewExportPayload(BaseModel):
    visualPreviewId: str | None = None


class ComparisonCreate(BaseModel):
    referenceArtifactId: str
    currentArtifactId: str
    notes: str = ""
    status: str = "requires_external_analysis"


class ArtifactRoleUpdate(BaseModel):
    role: str | None = None


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

@app.get("/photogrammetry/realityscan/diagnostics")
def realityscan_diagnostics() -> dict:
    return realityscan_service.diagnostics()

@app.post("/projects/{project_id}/photogrammetry/realityscan/prepare")
def prepare_realityscan_job(project_id: str) -> dict:
    if not project_repository.get_project(project_id): raise HTTPException(status_code=404, detail="Project not found")
    try: return realityscan_service.prepare(project_id)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/projects/{project_id}/photogrammetry/realityscan/jobs")
def list_realityscan_jobs(project_id: str) -> list[dict]:
    if not project_repository.get_project(project_id): raise HTTPException(status_code=404, detail="Project not found")
    return photogrammetry_job_repository.list_jobs(project_id)


@app.get("/visual-preview/diagnostics", deprecated=True)
def visual_preview_diagnostics() -> dict:
    return visual_preview_service.diagnostics()


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


@app.get("/projects/{project_id}/jobs/{job_key}/status")
def get_job_status(project_id: str, job_key: str) -> dict:
    if not project_repository.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    status = job_progress_service.get(project_id, job_key)
    if job_key == "capture_processing" and status and status.get("status") == "running":
        capture = capture_repository.get_capture_metadata(project_id)
        if capture:
            return job_progress_service.complete(project_id, job_key, "Capture processing complete", warnings=capture.get("warnings") or [])
    if not status:
        return {
            "jobKey": job_key,
            "projectId": project_id,
            "status": "pending",
            "currentStage": "not_started",
            "currentStepLabel": "Not run yet.",
            "progressPercent": None,
            "startedAt": None,
            "updatedAt": None,
            "finishedAt": None,
            "elapsedSeconds": 0,
            "etaSeconds": None,
            "processedItems": None,
            "totalItems": None,
            "logTail": [],
            "warnings": [],
            "errors": [],
        }
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
        return reconstruction_service.run_sparse_reconstruction(
            project_id,
            payload.matchingMode if payload else "Auto",
            payload.frameSelectionMode if payload else "Balanced subset",
        )
    except reconstruction_service.ReconstructionError as exc:
        summary = reconstruction_service.reconstruction_summary(project_id)
        raise HTTPException(status_code=400, detail={"message": str(exc), "summary": summary}) from exc


@app.post("/projects/{project_id}/reconstruct/sparse/sweep")
def run_sparse_reconstruction_sweep(project_id: str) -> dict:
    if not project_repository.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return reconstruction_service.run_sparse_reconstruction_sweep(project_id)
    except reconstruction_service.ReconstructionError as exc:
        summary = reconstruction_service.reconstruction_summary(project_id)
        raise HTTPException(status_code=400, detail={"message": str(exc), "summary": summary}) from exc


@app.post("/projects/{project_id}/frame-selection/preview")
def preview_frame_selection(project_id: str, payload: FrameSelectionPreviewOptions | None = None) -> dict:
    preview = reconstruction_service.frame_selection_preview(project_id, payload.mode if payload else "Balanced subset")
    if not preview:
        raise HTTPException(status_code=404, detail="Project not found")
    return preview


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


@app.get("/projects/{project_id}/visual-preview-summary", deprecated=True)
def get_visual_preview_summary(project_id: str) -> dict:
    summary = visual_preview_service.visual_preview_summary(project_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Project not found")
    return summary


@app.post("/projects/{project_id}/model-artifacts/import")
async def import_model_artifact(project_id: str, file: UploadFile | None = File(default=None), artifactType: str = Form("unknown"),
                                sourceTool: str = Form("manual"), notes: str = Form(""), role: str | None = Form(default=None),
                                filePath: str | None = Form(default=None)) -> dict:
    if not project_repository.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if not file and not filePath:
        raise HTTPException(status_code=400, detail="Provide a model artifact file or filePath")
    try:
        if file:
            staging = PROCESSED_DIR / project_id / ".artifact_uploads"
            staging.mkdir(parents=True, exist_ok=True)
            source = staging / f"{uuid4()}_{Path(file.filename or 'artifact').name}"
            source.write_bytes(await file.read())
            result = model_artifact_service.import_artifact(project_id, source, file.filename or source.name, artifactType, sourceTool, notes, role)
            source.unlink(missing_ok=True)
        else:
            source = Path(filePath or "").expanduser().resolve()
            result = model_artifact_service.import_artifact(project_id, source, source.name, artifactType, sourceTool, notes, role)
        return result
    except model_artifact_service.ModelArtifactError as exc:
        job_progress_service.fail(project_id, "model_artifact_import", str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/projects/{project_id}/model-artifacts")
def list_model_artifacts(project_id: str) -> dict:
    if not project_repository.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return model_artifact_service.summary(project_id)


@app.get("/projects/{project_id}/model-artifacts/{artifact_id}")
def get_model_artifact(project_id: str, artifact_id: str) -> dict:
    artifact = model_artifact_repository.get_artifact(project_id, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Model artifact not found")
    return artifact


@app.post("/projects/{project_id}/model-artifacts/{artifact_id}/role")
def update_model_artifact_role(project_id: str, artifact_id: str, payload: ArtifactRoleUpdate) -> dict:
    if payload.role and payload.role not in model_artifact_service.ROLES:
        raise HTTPException(status_code=400, detail="Unsupported artifact role")
    artifact = model_artifact_repository.set_role(project_id, artifact_id, payload.role)
    if not artifact:
        raise HTTPException(status_code=404, detail="Model artifact not found")
    return artifact


@app.get("/projects/{project_id}/model-artifacts/{artifact_id}/download")
def download_model_artifact(project_id: str, artifact_id: str) -> FileResponse:
    artifact = model_artifact_repository.get_artifact(project_id, artifact_id)
    path = Path(artifact["storagePath"]) if artifact else None
    if not artifact or not path or not path.is_file() or PROCESSED_DIR.resolve() not in path.resolve().parents:
        raise HTTPException(status_code=404, detail="Model artifact not found")
    return FileResponse(path, media_type="application/octet-stream", filename=artifact["fileName"])


@app.post("/projects/{project_id}/comparisons")
def create_comparison(project_id: str, payload: ComparisonCreate) -> dict:
    if not project_repository.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if payload.status not in {"pending", "ready", "requires_external_analysis", "completed", "failed"}:
        raise HTTPException(status_code=400, detail="Unsupported comparison status")
    if payload.referenceArtifactId == payload.currentArtifactId:
        raise HTTPException(status_code=400, detail="Comparison requires two distinct artifacts")
    reference = model_artifact_repository.get_artifact(project_id, payload.referenceArtifactId); current = model_artifact_repository.get_artifact(project_id, payload.currentArtifactId)
    if not reference or not current:
        raise HTTPException(status_code=404, detail="Comparison artifact not found")
    if not model_artifact_service.comparison_candidate(reference)["measurementCandidate"] or not model_artifact_service.comparison_candidate(current)["measurementCandidate"]:
        raise HTTPException(status_code=400, detail="Comparisons require two measurement-grade artifacts with available model files")
    analysis = comparison_analysis_service.metadata_analysis(reference, current)
    return model_artifact_service.comparison_detail(project_id, model_artifact_repository.add_comparison(project_id, payload.referenceArtifactId, payload.currentArtifactId, payload.status, payload.notes, analysis))


@app.get("/projects/{project_id}/comparisons")
def list_comparisons(project_id: str) -> list[dict]:
    if not project_repository.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return [model_artifact_service.comparison_detail(project_id, item) for item in model_artifact_repository.list_comparisons(project_id)]


@app.get("/projects/{project_id}/comparisons/{comparison_id}")
def get_comparison(project_id: str, comparison_id: str) -> dict:
    comparison = model_artifact_repository.get_comparison(project_id, comparison_id)
    if not comparison:
        raise HTTPException(status_code=404, detail="Comparison not found")
    return model_artifact_service.comparison_detail(project_id, comparison)


@app.post("/projects/{project_id}/visual-preview/prepare", deprecated=True)
def prepare_visual_preview(project_id: str) -> dict:
    try:
        return visual_preview_service.prepare_visual_preview(project_id)
    except visual_preview_service.VisualPreviewError as exc:
        status_code = 404 if str(exc) == "Project not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@app.post("/projects/{project_id}/visual-preview/train", deprecated=True)
def train_visual_preview(project_id: str, payload: VisualPreviewTrainPayload | None = None) -> dict:
    try:
        return visual_preview_service.train_visual_preview(
            project_id,
            visual_preview_id=payload.visualPreviewId if payload else None,
            attempt_id=payload.attemptId if payload else None,
            max_iterations=payload.maxIterations if payload else None,
            preset=(payload.trainingPreset or payload.preset) if payload else visual_preview_service.DEFAULT_TRAINING_PRESET,
        )
    except visual_preview_service.VisualPreviewError as exc:
        status_code = 404 if str(exc) == "Project not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@app.get("/projects/{project_id}/visual-preview/training-status", deprecated=True)
def get_visual_preview_training_status(project_id: str) -> dict:
    try:
        return visual_preview_service.training_status(project_id)
    except visual_preview_service.VisualPreviewError as exc:
        status_code = 404 if str(exc) == "Project not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@app.post("/projects/{project_id}/visual-preview/export", deprecated=True)
def export_visual_preview(project_id: str, payload: VisualPreviewExportPayload | None = None) -> dict:
    try:
        return visual_preview_service.export_visual_preview(
            project_id,
            visual_preview_id=payload.visualPreviewId if payload else None,
        )
    except visual_preview_service.VisualPreviewError as exc:
        status_code = 404 if str(exc) == "Project not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@app.get("/projects/{project_id}/visual-preview/splat-file/metadata", deprecated=True)
def get_visual_preview_splat_metadata(project_id: str, visual_preview_id: str | None = None) -> dict:
    try:
        return visual_preview_service.exported_splat_metadata(project_id, visual_preview_id)
    except visual_preview_service.VisualPreviewError as exc:
        status_code = 404 if str(exc) == "Project not found" or "manifest not found" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@app.get("/projects/{project_id}/visual-preview/splat-file", deprecated=True)
def download_visual_preview_splat(project_id: str, visual_preview_id: str | None = None) -> FileResponse:
    try:
        splat_path = visual_preview_service.exported_splat_file(project_id, visual_preview_id)
    except visual_preview_service.VisualPreviewError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(
        path=splat_path,
        media_type="application/octet-stream",
        filename=splat_path.name,
    )


@app.get("/projects/{project_id}/point-cloud")
def get_point_cloud(project_id: str, max_points: int = 50000, attempt_id: str | None = None) -> dict:
    point_cloud = reconstruction_service.point_cloud(project_id, max_points=max_points, attempt_id=attempt_id)
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
def get_scene_analysis(project_id: str, attempt_id: str | None = None) -> dict:
    analysis = reconstruction_service.scene_analysis(project_id, attempt_id=attempt_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return analysis


@app.post("/projects/{project_id}/attempts/{attempt_id}/viewer-transform")
def save_attempt_viewer_transform(project_id: str, attempt_id: str, payload: ViewerTransformPayload) -> dict:
    if not project_repository.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    attempt = reconstruction_service.save_attempt_viewer_transform(
        project_id,
        attempt_id,
        {
            "rotationX": payload.rotationX,
            "rotationY": payload.rotationY,
            "rotationZ": payload.rotationZ,
            "flipX": payload.flipX,
            "flipY": payload.flipY,
            "flipZ": payload.flipZ,
            "scale": payload.scale,
            "offsetX": payload.offsetX,
            "offsetY": payload.offsetY,
            "offsetZ": payload.offsetZ,
        },
        payload.previewMode,
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return attempt


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
        raise HTTPException(status_code=409, detail="Sparse point cloud preview is not ready yet")
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
