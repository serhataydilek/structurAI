from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.database import UPLOADS_DIR, init_db
from app.repositories import annotation_repository, media_repository, project_repository
from app.services import processing_service, report_service

ALLOWED_IMAGE_PREFIX = "image/"
ALLOWED_VIDEO_PREFIX = "video/"

app = FastAPI(title="Structura AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    siteType: str = Field(..., min_length=1)
    description: str = ""


class AnnotationCreate(BaseModel):
    text: str = Field(..., min_length=1)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "product": "Structura AI"}


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

    return {"uploaded": saved, "count": len(saved)}


@app.post("/projects/{project_id}/process")
def start_processing(project_id: str) -> dict:
    if not project_repository.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    processing_service.start_processing(project_id)
    status = processing_service.get_status(project_id)
    return status


@app.get("/projects/{project_id}/status")
def get_status(project_id: str) -> dict:
    status = processing_service.get_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="Project not found")
    return status


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
