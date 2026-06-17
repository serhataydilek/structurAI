from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.database import get_connection


def _row_to_project(row: Any) -> dict[str, Any]:
    return dict(row)


def list_projects() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                projects.*,
                COUNT(media.id) AS mediaCount,
                capture_metadata.extracted_frame_count AS extractedFrameCount
            FROM projects
            LEFT JOIN media ON media.project_id = projects.id
            LEFT JOIN capture_metadata ON capture_metadata.project_id = projects.id
            GROUP BY projects.id
            ORDER BY projects.created_at DESC
            """
        ).fetchall()
    return [_row_to_project(row) for row in rows]


def create_project(name: str, site_type: str, description: str) -> dict[str, Any]:
    project_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    scan_type = "Interior Prototype" if site_type in {"Condo Interior", "Apartment", "Office"} else "Building Scan"
    project = {
        "id": project_id,
        "name": name,
        "site_type": site_type,
        "description": description or "",
        "scan_type": scan_type,
        "status": "Draft",
        "created_at": created_at,
        "processing_started_at": None,
    }
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO projects (id, name, site_type, description, scan_type, status, created_at, processing_started_at)
            VALUES (:id, :name, :site_type, :description, :scan_type, :status, :created_at, :processing_started_at)
            """,
            project,
        )
    return project


def get_project(project_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _row_to_project(row) if row else None


def set_processing(project_id: str) -> dict[str, Any] | None:
    started_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE projects SET status = ?, processing_started_at = ? WHERE id = ?",
            ("Processing", started_at, project_id),
        )
    return get_project(project_id)


def set_media_uploaded(project_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        conn.execute("UPDATE projects SET status = ? WHERE id = ? AND status = ?", ("Media Uploaded", project_id, "Draft"))
    return get_project(project_id)


def set_ready(project_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        conn.execute("UPDATE projects SET status = ? WHERE id = ?", ("Ready", project_id))
    return get_project(project_id)


def set_status(project_id: str, status: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        conn.execute("UPDATE projects SET status = ? WHERE id = ?", (status, project_id))
    return get_project(project_id)


def delete_project(project_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM capture_metadata WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM reconstruction_metadata WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM annotations WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM media WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))


def reset_all_projects() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM capture_metadata")
        conn.execute("DELETE FROM reconstruction_metadata")
        conn.execute("DELETE FROM annotations")
        conn.execute("DELETE FROM media")
        conn.execute("DELETE FROM projects")
