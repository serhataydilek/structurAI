from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.database import get_connection


def list_media(project_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM media WHERE project_id = ? ORDER BY created_at ASC",
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def count_video(project_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM media WHERE project_id = ? AND media_type = 'video'",
            (project_id,),
        ).fetchone()
    return int(row["count"])


def add_media(
    project_id: str,
    filename: str,
    original_filename: str,
    content_type: str,
    media_type: str,
    size_bytes: int,
) -> dict[str, Any]:
    item = {
        "id": str(uuid4()),
        "project_id": project_id,
        "filename": filename,
        "original_filename": original_filename,
        "content_type": content_type,
        "media_type": media_type,
        "size_bytes": size_bytes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO media (id, project_id, filename, original_filename, content_type, media_type, size_bytes, created_at)
            VALUES (:id, :project_id, :filename, :original_filename, :content_type, :media_type, :size_bytes, :created_at)
            """,
            item,
        )
    return item
