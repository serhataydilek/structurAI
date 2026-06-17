from datetime import datetime, timezone
import json
from typing import Any

from app.database import get_connection


def _decode(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["warnings"] = json.loads(item.pop("warnings_json") or "[]")
    item["sharpness_available"] = bool(item.get("sharpness_available", 1))
    return item


def upsert_capture_metadata(
    *,
    project_id: str,
    uploaded_media_count: int,
    extracted_frame_count: int,
    image_count: int,
    video_count: int,
    selected_fps_mode: str,
    extraction_fps: int,
    average_sharpness: float | None,
    blurry_frame_count: int,
    blurry_frame_percentage: float,
    sharpness_available: bool,
    workspace_path: str,
    extraction_method: str,
    warnings: list[str],
    next_step: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "project_id": project_id,
        "uploaded_media_count": uploaded_media_count,
        "extracted_frame_count": extracted_frame_count,
        "image_count": image_count,
        "video_count": video_count,
        "selected_fps_mode": selected_fps_mode,
        "extraction_fps": extraction_fps,
        "average_sharpness": average_sharpness,
        "blurry_frame_count": blurry_frame_count,
        "blurry_frame_percentage": blurry_frame_percentage,
        "sharpness_available": 1 if sharpness_available else 0,
        "workspace_path": workspace_path,
        "extraction_method": extraction_method,
        "warnings_json": json.dumps(warnings),
        "next_step": next_step,
        "created_at": now,
        "updated_at": now,
    }
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO capture_metadata (
                project_id, uploaded_media_count, extracted_frame_count, image_count,
                video_count, selected_fps_mode, extraction_fps, average_sharpness,
                blurry_frame_count, blurry_frame_percentage, sharpness_available,
                workspace_path, extraction_method, warnings_json, next_step,
                created_at, updated_at
            )
            VALUES (
                :project_id, :uploaded_media_count, :extracted_frame_count, :image_count,
                :video_count, :selected_fps_mode, :extraction_fps, :average_sharpness,
                :blurry_frame_count, :blurry_frame_percentage, :sharpness_available,
                :workspace_path, :extraction_method, :warnings_json, :next_step,
                :created_at, :updated_at
            )
            ON CONFLICT(project_id) DO UPDATE SET
                uploaded_media_count = excluded.uploaded_media_count,
                extracted_frame_count = excluded.extracted_frame_count,
                image_count = excluded.image_count,
                video_count = excluded.video_count,
                selected_fps_mode = excluded.selected_fps_mode,
                extraction_fps = excluded.extraction_fps,
                average_sharpness = excluded.average_sharpness,
                blurry_frame_count = excluded.blurry_frame_count,
                blurry_frame_percentage = excluded.blurry_frame_percentage,
                sharpness_available = excluded.sharpness_available,
                workspace_path = excluded.workspace_path,
                extraction_method = excluded.extraction_method,
                warnings_json = excluded.warnings_json,
                next_step = excluded.next_step,
                updated_at = excluded.updated_at
            """,
            payload,
        )
    return get_capture_metadata(project_id) or {}


def get_capture_metadata(project_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM capture_metadata WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    return _decode(row) if row else None
