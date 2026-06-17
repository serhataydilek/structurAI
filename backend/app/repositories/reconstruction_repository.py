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


def _decode_attempt(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["attemptId"] = item.pop("attempt_id")
    item["projectId"] = item.pop("project_id")
    item["createdAt"] = item.pop("created_at")
    item["extractedFrameCount"] = item.pop("extracted_frame_count")
    item["sourceFrameCount"] = item.pop("source_frame_count", item["extractedFrameCount"])
    item["selectedFrameCount"] = item.pop("selected_frame_count", item["extractedFrameCount"])
    item["frameSelectionMode"] = item.pop("frame_selection_mode", "All frames")
    item["selectedFrameFolder"] = item.pop("selected_frame_folder", None)
    item["registeredImageCount"] = item.pop("registered_image_count")
    item["registrationRatio"] = item.pop("registration_ratio")
    item["sparsePointCount"] = item.pop("sparse_point_count")
    item["sparseQualityLabel"] = item.pop("sparse_quality_label")
    item["matchingMode"] = item.pop("matching_mode")
    item["selectedFps"] = item.pop("selected_fps")
    item["extractionFps"] = item.pop("extraction_fps")
    item["outputPath"] = item.pop("output_path")
    item["logFiles"] = json.loads(item.pop("log_files_json") or "[]")
    item["sparseModelFolders"] = json.loads(item.pop("sparse_model_folders_json") or "[]")
    item["sceneAnalysisSummary"] = json.loads(item.pop("scene_analysis_summary_json") or "{}")
    item["viewerTransform"] = json.loads(item.pop("viewer_transform_json", "{}") or "{}")
    item["viewerPreviewMode"] = item.pop("viewer_preview_mode", "auto") or "auto"
    item["isBestAttempt"] = bool(item.pop("is_best_attempt"))
    item["failureReason"] = item.pop("failure_reason")
    item.pop("updated_at", None)
    return item


def upsert_attempt(
    *,
    attempt_id: str,
    project_id: str,
    extracted_frame_count: int,
    source_frame_count: int | None = None,
    selected_frame_count: int | None = None,
    frame_selection_mode: str = "All frames",
    selected_frame_folder: str | None = None,
    registered_image_count: int,
    registration_ratio: float,
    sparse_point_count: int,
    sparse_quality_label: str,
    matching_mode: str,
    selected_fps: str,
    extraction_fps: int,
    status: str,
    output_path: str | None,
    log_files: list[str],
    sparse_model_folders: list[str],
    scene_analysis_summary: dict[str, Any],
    is_best_attempt: bool = False,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO reconstruction_attempts (
                attempt_id, project_id, created_at, extracted_frame_count, registered_image_count,
                source_frame_count, selected_frame_count, frame_selection_mode, selected_frame_folder,
                registration_ratio, sparse_point_count, sparse_quality_label, matching_mode,
                selected_fps, extraction_fps, status, output_path, log_files_json,
                sparse_model_folders_json, scene_analysis_summary_json, viewer_transform_json, viewer_preview_mode, is_best_attempt,
                failure_reason, updated_at
            )
            VALUES (
                :attempt_id, :project_id, :created_at, :extracted_frame_count, :registered_image_count,
                :source_frame_count, :selected_frame_count, :frame_selection_mode, :selected_frame_folder,
                :registration_ratio, :sparse_point_count, :sparse_quality_label, :matching_mode,
                :selected_fps, :extraction_fps, :status, :output_path, :log_files_json,
                :sparse_model_folders_json, :scene_analysis_summary_json, '{}', 'auto', :is_best_attempt,
                :failure_reason, :updated_at
            )
            ON CONFLICT(attempt_id) DO UPDATE SET
                extracted_frame_count = excluded.extracted_frame_count,
                source_frame_count = excluded.source_frame_count,
                selected_frame_count = excluded.selected_frame_count,
                frame_selection_mode = excluded.frame_selection_mode,
                selected_frame_folder = excluded.selected_frame_folder,
                registered_image_count = excluded.registered_image_count,
                registration_ratio = excluded.registration_ratio,
                sparse_point_count = excluded.sparse_point_count,
                sparse_quality_label = excluded.sparse_quality_label,
                matching_mode = excluded.matching_mode,
                selected_fps = excluded.selected_fps,
                extraction_fps = excluded.extraction_fps,
                status = excluded.status,
                output_path = excluded.output_path,
                log_files_json = excluded.log_files_json,
                sparse_model_folders_json = excluded.sparse_model_folders_json,
                scene_analysis_summary_json = excluded.scene_analysis_summary_json,
                is_best_attempt = excluded.is_best_attempt,
                failure_reason = excluded.failure_reason,
                updated_at = excluded.updated_at
            """,
            {
                "attempt_id": attempt_id,
                "project_id": project_id,
                "created_at": now,
                "extracted_frame_count": extracted_frame_count,
                "source_frame_count": source_frame_count if source_frame_count is not None else extracted_frame_count,
                "selected_frame_count": selected_frame_count if selected_frame_count is not None else extracted_frame_count,
                "frame_selection_mode": frame_selection_mode,
                "selected_frame_folder": selected_frame_folder,
                "registered_image_count": registered_image_count,
                "registration_ratio": registration_ratio,
                "sparse_point_count": sparse_point_count,
                "sparse_quality_label": sparse_quality_label,
                "matching_mode": matching_mode,
                "selected_fps": selected_fps,
                "extraction_fps": extraction_fps,
                "status": status,
                "output_path": output_path,
                "log_files_json": json.dumps(log_files),
                "sparse_model_folders_json": json.dumps(sparse_model_folders),
                "scene_analysis_summary_json": json.dumps(scene_analysis_summary),
                "is_best_attempt": 1 if is_best_attempt else 0,
                "failure_reason": failure_reason,
                "updated_at": now,
            },
        )
    return get_attempt(attempt_id) or {}


def create_frame_selection(
    *,
    selection_id: str,
    project_id: str,
    mode: str,
    source_frame_count: int,
    selected_frame_count: int,
    average_selected_sharpness: float | None,
    selected_frame_filenames: list[str],
    selected_frame_folder: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO reconstruction_frame_selections (
                selection_id, project_id, mode, source_frame_count, selected_frame_count,
                average_selected_sharpness, selected_frame_filenames_json, selected_frame_folder, created_at
            )
            VALUES (
                :selection_id, :project_id, :mode, :source_frame_count, :selected_frame_count,
                :average_selected_sharpness, :selected_frame_filenames_json, :selected_frame_folder, :created_at
            )
            """,
            {
                "selection_id": selection_id,
                "project_id": project_id,
                "mode": mode,
                "source_frame_count": source_frame_count,
                "selected_frame_count": selected_frame_count,
                "average_selected_sharpness": average_selected_sharpness,
                "selected_frame_filenames_json": json.dumps(selected_frame_filenames),
                "selected_frame_folder": selected_frame_folder,
                "created_at": now,
            },
        )
    return {
        "selectionId": selection_id,
        "projectId": project_id,
        "mode": mode,
        "sourceFrameCount": source_frame_count,
        "selectedFrameCount": selected_frame_count,
        "averageSelectedSharpness": average_selected_sharpness,
        "selectedFrameFilenames": selected_frame_filenames,
        "selectedFrameFolder": selected_frame_folder,
        "createdAt": now,
    }


def get_attempt(attempt_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM reconstruction_attempts WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
    return _decode_attempt(row) if row else None


def list_attempts(project_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM reconstruction_attempts WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    return [_decode_attempt(row) for row in rows]


def mark_best_attempt(project_id: str, attempt_id: str | None) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE reconstruction_attempts SET is_best_attempt = 0 WHERE project_id = ?", (project_id,))
        if attempt_id:
            conn.execute(
                "UPDATE reconstruction_attempts SET is_best_attempt = 1 WHERE project_id = ? AND attempt_id = ?",
                (project_id, attempt_id),
            )


def update_attempt_viewer_state(
    attempt_id: str,
    *,
    viewer_transform: dict[str, Any],
    viewer_preview_mode: str = "auto",
) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE reconstruction_attempts SET
                viewer_transform_json = :viewer_transform_json,
                viewer_preview_mode = :viewer_preview_mode,
                updated_at = :updated_at
            WHERE attempt_id = :attempt_id
            """,
            {
                "attempt_id": attempt_id,
                "viewer_transform_json": json.dumps(viewer_transform),
                "viewer_preview_mode": viewer_preview_mode,
                "updated_at": now,
            },
        )
    return get_attempt(attempt_id)
