from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.database import get_connection

DEFAULT_ANNOTATIONS = [
    "Window wall",
    "Scan coverage needs improvement near corner",
    "Potential renovation area",
]


def list_annotations(project_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM annotations WHERE project_id = ? ORDER BY created_at ASC",
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_annotation(project_id: str, text: str) -> dict[str, Any]:
    item = {
        "id": str(uuid4()),
        "project_id": project_id,
        "text": text.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO annotations (id, project_id, text, created_at)
            VALUES (:id, :project_id, :text, :created_at)
            """,
            item,
        )
    return item


def seed_default_annotations(project_id: str) -> None:
    for text in DEFAULT_ANNOTATIONS:
        add_annotation(project_id, text)
