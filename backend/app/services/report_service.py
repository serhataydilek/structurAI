from typing import Any

from app.repositories import annotation_repository, media_repository, project_repository


def build_report(project_id: str) -> dict[str, Any] | None:
    project = project_repository.get_project(project_id)
    if not project:
        return None

    annotations = annotation_repository.list_annotations(project_id)
    media = media_repository.list_media(project_id)

    return {
        "projectName": project["name"],
        "projectId": project_id,
        "uploadedMediaCount": len(media),
        "processingStatus": project["status"],
        "detectedOutput": "Interactive 3D model",
        "annotations": annotations,
        "limitations": [
            "Measurements are approximate in this prototype",
            "Full building-scale reconstruction will be added in later phases",
        ],
    }
