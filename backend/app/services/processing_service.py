from datetime import datetime, timezone
from typing import Any

from app.repositories import project_repository

PIPELINE_STEPS = [
    "Upload received",
    "Extracting frames",
    "Estimating camera positions",
    "Generating point cloud",
    "Building 3D model",
    "Exporting digital twin",
]

TOTAL_SECONDS = 18


def start_processing(project_id: str) -> dict[str, Any] | None:
    return project_repository.set_processing(project_id)


def get_status(project_id: str) -> dict[str, Any] | None:
    project = project_repository.get_project(project_id)
    if not project:
        return None

    if project["status"] == "Ready":
        return {
            "projectId": project_id,
            "status": "Ready",
            "progress": 100,
            "currentStep": PIPELINE_STEPS[-1],
            "steps": PIPELINE_STEPS,
        }

    if project["status"] != "Processing" or not project["processing_started_at"]:
        return {
            "projectId": project_id,
            "status": project["status"],
            "progress": 0,
            "currentStep": PIPELINE_STEPS[0],
            "steps": PIPELINE_STEPS,
        }

    started_at = datetime.fromisoformat(project["processing_started_at"])
    elapsed = max(0.0, (datetime.now(timezone.utc) - started_at).total_seconds())
    progress = min(100, int((elapsed / TOTAL_SECONDS) * 100))

    if progress >= 100:
        project_repository.set_ready(project_id)
        return {
            "projectId": project_id,
            "status": "Ready",
            "progress": 100,
            "currentStep": PIPELINE_STEPS[-1],
            "steps": PIPELINE_STEPS,
        }

    step_index = min(len(PIPELINE_STEPS) - 1, int(progress / (100 / len(PIPELINE_STEPS))))
    return {
        "projectId": project_id,
        "status": "Processing",
        "progress": progress,
        "currentStep": PIPELINE_STEPS[step_index],
        "steps": PIPELINE_STEPS,
    }
