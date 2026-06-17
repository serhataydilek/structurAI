from datetime import datetime, timezone
import json
from typing import Any

from app.database import get_connection


def _decode(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["colmap_available"] = bool(item["colmap_available"])
    item["sparse_output_exists"] = bool(item["sparse_output_exists"])
    item["dense_output_exists"] = bool(item.get("dense_output_exists", 0))
    item["selected_fps_mode"] = item.get("selected_fps_mode") or "Balanced"
    item["extraction_fps"] = item.get("extraction_fps") or 2
    item["matching_mode"] = item.get("matching_mode") or "Photo Exhaustive"
    item["sparse_model_folders"] = json.loads(item.pop("sparse_model_folders_json") or "[]")
    item["log_files"] = json.loads(item.pop("log_files_json") or "[]")
    item["warnings"] = json.loads(item.pop("warnings_json") or "[]")
    item["dense_log_files"] = json.loads(item.pop("dense_log_files_json", "[]") or "[]")
    item["dense_warnings"] = json.loads(item.pop("dense_warnings_json", "[]") or "[]")
    return item


def upsert_reconstruction_metadata(
    *,
    project_id: str,
    status: str,
    colmap_available: bool,
    colmap_version: str | None,
    input_frame_count: int,
    sparse_output_exists: bool,
    sparse_model_folders: list[str],
    log_files: list[str],
    warnings: list[str],
    error_message: str | None,
    selected_fps_mode: str = "Balanced",
    extraction_fps: int = 2,
    matching_mode: str = "Photo Exhaustive",
    started_at: str | None = None,
    completed_at: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "project_id": project_id,
        "status": status,
        "colmap_available": 1 if colmap_available else 0,
        "colmap_version": colmap_version,
        "input_frame_count": input_frame_count,
        "selected_fps_mode": selected_fps_mode,
        "extraction_fps": extraction_fps,
        "matching_mode": matching_mode,
        "sparse_output_exists": 1 if sparse_output_exists else 0,
        "sparse_model_folders_json": json.dumps(sparse_model_folders),
        "log_files_json": json.dumps(log_files),
        "warnings_json": json.dumps(warnings),
        "error_message": error_message,
        "started_at": started_at,
        "completed_at": completed_at,
        "updated_at": now,
    }
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO reconstruction_metadata (
                project_id, status, colmap_available, colmap_version, input_frame_count,
                selected_fps_mode, extraction_fps, matching_mode, sparse_output_exists,
                sparse_model_folders_json, log_files_json,
                warnings_json, error_message, started_at, completed_at, updated_at
            )
            VALUES (
                :project_id, :status, :colmap_available, :colmap_version, :input_frame_count,
                :selected_fps_mode, :extraction_fps, :matching_mode, :sparse_output_exists,
                :sparse_model_folders_json, :log_files_json,
                :warnings_json, :error_message, :started_at, :completed_at, :updated_at
            )
            ON CONFLICT(project_id) DO UPDATE SET
                status = excluded.status,
                colmap_available = excluded.colmap_available,
                colmap_version = excluded.colmap_version,
                input_frame_count = excluded.input_frame_count,
                selected_fps_mode = excluded.selected_fps_mode,
                extraction_fps = excluded.extraction_fps,
                matching_mode = excluded.matching_mode,
                sparse_output_exists = excluded.sparse_output_exists,
                sparse_model_folders_json = excluded.sparse_model_folders_json,
                log_files_json = excluded.log_files_json,
                warnings_json = excluded.warnings_json,
                error_message = excluded.error_message,
                started_at = COALESCE(excluded.started_at, reconstruction_metadata.started_at),
                completed_at = excluded.completed_at,
                updated_at = excluded.updated_at
            """,
            payload,
        )
    return get_reconstruction_metadata(project_id) or {}


def get_reconstruction_metadata(project_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM reconstruction_metadata WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    return _decode(row) if row else None


def update_dense_metadata(
    *,
    project_id: str,
    dense_status: str,
    dense_output_exists: bool,
    dense_point_count: int,
    dense_output_path: str | None,
    dense_log_files: list[str],
    dense_warnings: list[str],
    dense_error_message: str | None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE reconstruction_metadata SET
                dense_status = :dense_status,
                dense_output_exists = :dense_output_exists,
                dense_point_count = :dense_point_count,
                dense_output_path = :dense_output_path,
                dense_log_files_json = :dense_log_files_json,
                dense_warnings_json = :dense_warnings_json,
                dense_error_message = :dense_error_message,
                updated_at = :updated_at
            WHERE project_id = :project_id
            """,
            {
                "project_id": project_id,
                "dense_status": dense_status,
                "dense_output_exists": 1 if dense_output_exists else 0,
                "dense_point_count": dense_point_count,
                "dense_output_path": dense_output_path,
                "dense_log_files_json": json.dumps(dense_log_files),
                "dense_warnings_json": json.dumps(dense_warnings),
                "dense_error_message": dense_error_message,
                "updated_at": now,
            },
        )
    return get_reconstruction_metadata(project_id) or {}
