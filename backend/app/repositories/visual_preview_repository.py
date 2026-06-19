from datetime import datetime, timezone
import json
from typing import Any

from app.database import get_connection


def _decode(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["visualPreviewId"] = item.pop("visual_preview_id")
    item["projectId"] = item.pop("project_id")
    item["attemptId"] = item.pop("attempt_id")
    item["previewType"] = item.pop("preview_type")
    item["sourceAttemptId"] = item.pop("source_attempt_id")
    item["createdAt"] = item.pop("created_at")
    item["updatedAt"] = item.pop("updated_at")
    item["outputPath"] = item.pop("output_path")
    item["manifestPath"] = item.pop("manifest_path")
    item["trainingStatus"] = item.pop("training_status", "not_started")
    item["exportStatus"] = item.pop("export_status", "not_started")
    item["trainingStartedAt"] = item.pop("training_started_at", None)
    item["trainingFinishedAt"] = item.pop("training_finished_at", None)
    item["trainingLogPath"] = item.pop("training_log_path", None)
    item["exportLogPath"] = item.pop("export_log_path", None)
    item["nerfstudioConfigPath"] = item.pop("nerfstudio_config_path", None)
    item["splatOutputPath"] = item.pop("splat_output_path", None)
    item["splatOutputSizeBytes"] = item.pop("splat_output_size_bytes", None)
    item["viewerAssetPath"] = item.pop("viewer_asset_path", None)
    item["errorMessage"] = item.pop("error_message")
    item["summaryJson"] = json.loads(item.pop("summary_json") or "{}")
    item["trainingPreset"] = item["summaryJson"].get("trainingPreset") or item["summaryJson"].get("preset")
    item["maxIterations"] = item["summaryJson"].get("maxIterations")
    return item


def upsert_visual_preview(
    *,
    visual_preview_id: str,
    project_id: str,
    attempt_id: str,
    status: str,
    preview_type: str,
    source_attempt_id: str,
    output_path: str | None,
    manifest_path: str | None,
    error_message: str | None,
    summary_json: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT created_at FROM visual_preview_outputs WHERE visual_preview_id = ?",
            (visual_preview_id,),
        ).fetchone()
        created_at = existing["created_at"] if existing else now
        conn.execute(
            """
            INSERT INTO visual_preview_outputs (
                visual_preview_id, project_id, attempt_id, status, preview_type, source_attempt_id,
                created_at, updated_at, output_path, manifest_path, error_message, summary_json
            )
            VALUES (
                :visual_preview_id, :project_id, :attempt_id, :status, :preview_type, :source_attempt_id,
                :created_at, :updated_at, :output_path, :manifest_path, :error_message, :summary_json
            )
            ON CONFLICT(visual_preview_id) DO UPDATE SET
                status = excluded.status,
                preview_type = excluded.preview_type,
                source_attempt_id = excluded.source_attempt_id,
                updated_at = excluded.updated_at,
                output_path = excluded.output_path,
                manifest_path = excluded.manifest_path,
                error_message = excluded.error_message,
                summary_json = excluded.summary_json
            """,
            {
                "visual_preview_id": visual_preview_id,
                "project_id": project_id,
                "attempt_id": attempt_id,
                "status": status,
                "preview_type": preview_type,
                "source_attempt_id": source_attempt_id,
                "created_at": created_at,
                "updated_at": now,
                "output_path": output_path,
                "manifest_path": manifest_path,
                "error_message": error_message,
                "summary_json": json.dumps(summary_json),
            },
        )
    return get_visual_preview(visual_preview_id) or {}


def update_job_state(
    visual_preview_id: str,
    *,
    status: str | None = None,
    training_status: str | None = None,
    export_status: str | None = None,
    training_started_at: str | None = None,
    training_finished_at: str | None = None,
    training_log_path: str | None = None,
    export_log_path: str | None = None,
    nerfstudio_config_path: str | None = None,
    splat_output_path: str | None = None,
    splat_output_size_bytes: int | None = None,
    viewer_asset_path: str | None = None,
    error_message: str | None = None,
    summary_json: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    current = get_visual_preview(visual_preview_id)
    if not current:
        return None
    now = datetime.now(timezone.utc).isoformat()
    merged_summary = dict(current.get("summaryJson") or {})
    if summary_json:
        merged_summary.update(summary_json)
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE visual_preview_outputs SET
                status = COALESCE(:status, status),
                training_status = COALESCE(:training_status, training_status),
                export_status = COALESCE(:export_status, export_status),
                training_started_at = COALESCE(:training_started_at, training_started_at),
                training_finished_at = COALESCE(:training_finished_at, training_finished_at),
                training_log_path = COALESCE(:training_log_path, training_log_path),
                export_log_path = COALESCE(:export_log_path, export_log_path),
                nerfstudio_config_path = COALESCE(:nerfstudio_config_path, nerfstudio_config_path),
                splat_output_path = COALESCE(:splat_output_path, splat_output_path),
                splat_output_size_bytes = COALESCE(:splat_output_size_bytes, splat_output_size_bytes),
                viewer_asset_path = COALESCE(:viewer_asset_path, viewer_asset_path),
                error_message = :error_message,
                summary_json = :summary_json,
                updated_at = :updated_at
            WHERE visual_preview_id = :visual_preview_id
            """,
            {
                "visual_preview_id": visual_preview_id,
                "status": status,
                "training_status": training_status,
                "export_status": export_status,
                "training_started_at": training_started_at,
                "training_finished_at": training_finished_at,
                "training_log_path": training_log_path,
                "export_log_path": export_log_path,
                "nerfstudio_config_path": nerfstudio_config_path,
                "splat_output_path": splat_output_path,
                "splat_output_size_bytes": splat_output_size_bytes,
                "viewer_asset_path": viewer_asset_path,
                "error_message": error_message,
                "summary_json": json.dumps(merged_summary),
                "updated_at": now,
            },
        )
    return get_visual_preview(visual_preview_id)


def get_visual_preview(visual_preview_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM visual_preview_outputs WHERE visual_preview_id = ?",
            (visual_preview_id,),
        ).fetchone()
    return _decode(row) if row else None


def latest_for_project(project_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM visual_preview_outputs
            WHERE project_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
    return _decode(row) if row else None
