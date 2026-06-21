from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.database import get_connection


JOB_STATUSES = {
    "pending",
    "preparing",
    "running",
    "importing",
    "completed",
    "failed",
    "cancelled",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job(row: Any) -> dict[str, Any] | None:
    return dict(row) if row else None


def _validate_status(status: str) -> None:
    if status not in JOB_STATUSES:
        raise ValueError(f"Unsupported RealityScan job status: {status}")


def create_job(
    project_id: str,
    job_dir: str,
    *,
    job_id: str | None = None,
    status: str = "pending",
    progress: float | None = None,
    eta_seconds: float | None = None,
    elapsed_seconds: float | None = None,
    stage: str | None = None,
    image_count: int | None = None,
    images_dir: str | None = None,
    export_dir: str | None = None,
    progress_file_path: str | None = None,
    project_file_path: str | None = None,
    exported_model_path: str | None = None,
) -> dict[str, Any]:
    _validate_status(status)
    job_id = job_id or str(uuid4())
    created_at = _now()
    job = {
        "id": job_id,
        "project_id": project_id,
        "status": status,
        "progress": progress,
        "eta_seconds": eta_seconds,
        "elapsed_seconds": elapsed_seconds,
        "stage": stage,
        "image_count": image_count,
        "job_dir": job_dir,
        "images_dir": images_dir,
        "export_dir": export_dir,
        "progress_file_path": progress_file_path,
        "project_file_path": project_file_path,
        "exported_model_path": exported_model_path,
        "error_message": None,
        "created_at": created_at,
        "started_at": created_at if status in {"preparing", "running", "importing"} else None,
        "completed_at": created_at if status in {"completed", "failed", "cancelled"} else None,
    }
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO realityscan_jobs (
                id, project_id, status, progress, eta_seconds, elapsed_seconds, stage,
                image_count, job_dir, images_dir, export_dir, progress_file_path,
                project_file_path, exported_model_path, error_message, created_at,
                started_at, completed_at
            ) VALUES (
                :id, :project_id, :status, :progress, :eta_seconds, :elapsed_seconds, :stage,
                :image_count, :job_dir, :images_dir, :export_dir, :progress_file_path,
                :project_file_path, :exported_model_path, :error_message, :created_at,
                :started_at, :completed_at
            )
            """,
            job,
        )
    return job


def get_job(job_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM realityscan_jobs WHERE id = ?", (job_id,)).fetchone()
    return _job(row)


def get_latest_job_for_project(project_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM realityscan_jobs WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()
    return _job(row)


def list_jobs(project_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM realityscan_jobs WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    return [_job(row) for row in rows]


def update_job_status(
    job_id: str,
    status: str,
    *,
    stage: str | None = None,
) -> dict[str, Any] | None:
    _validate_status(status)
    started_at = _now() if status in {"preparing", "running", "importing"} else None
    completed_at = _now() if status in {"completed", "failed", "cancelled"} else None
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE realityscan_jobs
            SET status = ?, stage = COALESCE(?, stage),
                started_at = COALESCE(started_at, ?),
                completed_at = COALESCE(?, completed_at)
            WHERE id = ?
            """,
            (status, stage, started_at, completed_at, job_id),
        )
    return get_job(job_id)


def update_job_progress(
    job_id: str,
    progress: float | None,
    *,
    eta_seconds: float | None = None,
    elapsed_seconds: float | None = None,
    stage: str | None = None,
    raw_progress: float | None = None,
    raw_eta_seconds: float | None = None,
    raw_elapsed_seconds: float | None = None,
    raw_alg_id: str | None = None,
) -> dict[str, Any] | None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE realityscan_jobs
            SET progress = CASE
                    WHEN progress IS NULL THEN ?
                    WHEN ? IS NULL THEN progress
                    ELSE MAX(progress, ?)
                END,
                eta_seconds = ?, elapsed_seconds = ?, stage = COALESCE(?, stage),
                raw_progress = ?, raw_eta_seconds = ?, raw_elapsed_seconds = ?, raw_alg_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (progress, progress, progress, eta_seconds, elapsed_seconds, stage,
             raw_progress, raw_eta_seconds, raw_elapsed_seconds, raw_alg_id, _now(), job_id),
        )
    return get_job(job_id)


def mark_job_failed(job_id: str, error_message: str) -> dict[str, Any] | None:
    completed_at = _now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE realityscan_jobs
            SET status = 'failed', error_message = ?, completed_at = ?
            WHERE id = ?
            """,
            (error_message, completed_at, job_id),
        )
    return get_job(job_id)


def mark_job_completed(
    job_id: str,
    *,
    exported_model_path: str | None = None,
) -> dict[str, Any] | None:
    completed_at = _now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE realityscan_jobs
            SET status = 'completed', progress = 1.0,
                exported_model_path = COALESCE(?, exported_model_path),
                completed_at = ?
            WHERE id = ?
            """,
            (exported_model_path, completed_at, job_id),
        )
    return get_job(job_id)
