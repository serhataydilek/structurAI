"""Deterministic Blender-backed conversion of managed OBJ artifacts to viewer-ready GLB."""
from __future__ import annotations

import os
import json
from pathlib import Path
import subprocess
from threading import Thread
from uuid import uuid4

from app.database import PROCESSED_DIR
from app.repositories import model_artifact_repository
from app.services import job_progress_service

JOB_KEY = "model_preview"
BLENDER_CANDIDATES = tuple(Path(rf"C:\Program Files\Blender Foundation\Blender {version}\blender.exe") for version in ("4.3", "4.2", "4.1"))
REALITYSCAN_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "projects"


class ModelPreviewError(ValueError):
    pass


def diagnostics() -> dict:
    configured = os.getenv("BLENDER_EXE")
    candidate = Path(configured) if configured else next((path for path in BLENDER_CANDIDATES if path.is_file()), None)
    exists = bool(candidate and candidate.is_file())
    enabled = os.getenv("STRUCTURA_ENABLE_MODEL_PREVIEW", "").lower() == "true"
    notes = []
    if not enabled: notes.append("Set STRUCTURA_ENABLE_MODEL_PREVIEW=true to enable preview preparation.")
    if not exists: notes.append("Configure BLENDER_EXE or install Blender in a supported location.")
    return {"available": exists, "enabled": enabled, "blender_path": str(candidate) if candidate else None,
            "blender_exists": exists, "notes": notes}


def _read_report(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _inside_managed_storage(path: Path) -> bool:
    resolved = path.resolve()
    managed_roots = (PROCESSED_DIR.resolve(), REALITYSCAN_DATA_DIR.resolve())
    return any(root == resolved or root in resolved.parents for root in managed_roots)


def _source_obj(artifact: dict) -> Path:
    path = Path((artifact.get("bundle") or {}).get("mainObjPath") or artifact.get("primary_file_path") or artifact["storagePath"])
    if artifact.get("status") != "ready" or path.suffix.lower() != ".obj":
        raise ModelPreviewError("Preview preparation requires a ready OBJ model artifact")
    if not path.is_file() or not _inside_managed_storage(path):
        raise ModelPreviewError("Source artifact is not inside managed storage")
    return path


def prepare(project_id: str, artifact: dict) -> dict:
    source = _source_obj(artifact)
    info = diagnostics()
    if not info["enabled"] or not info["available"]:
        raise ModelPreviewError("Preview preparation requires Blender configuration")
    current = job_progress_service.get(project_id, JOB_KEY)
    if current and current.get("status") == "running":
        raise ModelPreviewError("A 3D preview is already being prepared")
    job_id = str(uuid4())
    folder = PROCESSED_DIR / project_id / "model_preview" / job_id
    folder.mkdir(parents=True, exist_ok=True)
    output, report, log = folder / "preview.glb", folder / "preview_report.json", folder / "blender.log"
    job_progress_service.start(project_id, JOB_KEY, "queued", "Preparing 3D preview", progress_percent=5)
    Thread(target=_run, args=(project_id, artifact, source, output, report, log, Path(info["blender_path"])), daemon=True).start()
    return status(project_id, artifact["artifactId"])


def _run(project_id: str, source_artifact: dict, source: Path, output: Path, report: Path, log: Path, blender: Path) -> None:
    try:
        job_progress_service.update(project_id, JOB_KEY, stage="launching_blender", label="Launching Blender", progress_percent=15)
        script = Path(__file__).resolve().parents[3] / "scripts" / "convert_obj_to_glb.py"
        command = [str(blender), "--background", "--python", str(script), "--", str(source), str(output), str(report)]
        job_progress_service.update(project_id, JOB_KEY, stage="converting_obj_to_glb", label="Converting OBJ to viewer-ready GLB", progress_percent=50)
        result = subprocess.run(command, capture_output=True, text=True, timeout=3600)
        log.write_text((result.stdout or "") + "\n" + (result.stderr or ""), encoding="utf-8")
        if result.returncode != 0 or not output.is_file():
            raise ModelPreviewError("Blender did not produce a viewer-ready GLB; see preview logs")
        job_progress_service.update(project_id, JOB_KEY, stage="registering_artifact", label="Registering viewer-ready artifact", progress_percent=90)
        report_data = _read_report(report)
        face_count = report_data.get("polygon_count")
        model_artifact_repository.add_artifact(
            project_id, "textured_mesh", "manual", output.name, output.stat().st_size, str(output),
            str(output.relative_to(PROCESSED_DIR)), "Derived viewer-ready GLB from RealityScan raw artifact", source_artifact.get("role"),
            {"faceCount": face_count, "statsPartial": True},
            {"bundleRootPath": str(output.parent), "mainGlbPath": str(output), "sourceObjPath": str(source), "previewReportPath": str(report)},
            source_type="postprocessing", model_format="glb", primary_file_path=str(output), status="ready",
            metadata={"artifactRole": "viewer_ready", "sourceArtifactId": source_artifact["artifactId"], "previewReportPath": str(report)},
        )
        job_progress_service.complete(project_id, JOB_KEY, "3D preview ready")
    except Exception as exc:
        job_progress_service.fail(project_id, JOB_KEY, str(exc))


def status(project_id: str, source_artifact_id: str | None = None) -> dict:
    progress = job_progress_service.get(project_id, JOB_KEY)
    artifacts = model_artifact_repository.list_artifacts(project_id)
    viewer = next((item for item in artifacts if item.get("artifactRole") == "viewer_ready" and (not source_artifact_id or item.get("sourceArtifactId") == source_artifact_id)), None)
    job_status = (progress or {}).get("status")
    status_value = job_status if job_status == "running" else ("completed" if viewer else (job_status or "not_started"))
    progress_percent = 100 if status_value == "completed" else (progress or {}).get("progressPercent")
    return {
        "status": status_value,
        "source_artifact_id": source_artifact_id,
        "viewer_artifact_id": viewer.get("artifactId") if viewer else None,
        "stage": "completed" if status_value == "completed" else (progress or {}).get("currentStage"),
        "progress": progress_percent,
        "progress_percent": progress_percent,
        "started_at": (progress or {}).get("startedAt"),
        "updated_at": viewer.get("updatedAt") if status_value == "completed" and viewer else (progress or {}).get("updatedAt"),
        "error_message": ((progress or {}).get("errors") or [None])[-1],
        "job_progress": progress,
    }
