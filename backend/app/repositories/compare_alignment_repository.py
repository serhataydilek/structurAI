from datetime import datetime, timezone

from app.database import get_connection


DEFAULT_ALIGNMENT = {
    "positionX": 0.0,
    "positionY": 0.0,
    "positionZ": 0.0,
    "rotationYDegrees": 0.0,
    "scale": 1.0,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _alignment(row) -> dict:
    if not row:
        return DEFAULT_ALIGNMENT.copy()
    return {
        "positionX": row["position_x"],
        "positionY": row["position_y"],
        "positionZ": row["position_z"],
        "rotationYDegrees": row["rotation_y_degrees"],
        "scale": row["scale"],
        "updatedAt": row["updated_at"],
    }


def get_alignment(project_id: str) -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM project_compare_alignments WHERE project_id = ?", (project_id,)).fetchone()
    return _alignment(row)


def save_alignment(project_id: str, alignment: dict) -> dict:
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO project_compare_alignments (project_id, position_x, position_y, position_z, rotation_y_degrees, scale, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(project_id) DO UPDATE SET position_x = excluded.position_x, position_y = excluded.position_y,
               position_z = excluded.position_z, rotation_y_degrees = excluded.rotation_y_degrees, scale = excluded.scale,
               updated_at = excluded.updated_at""",
            (project_id, alignment["positionX"], alignment["positionY"], alignment["positionZ"], alignment["rotationYDegrees"], alignment["scale"], now),
        )
    return get_alignment(project_id)


def delete_alignment(project_id: str) -> dict:
    with get_connection() as conn:
        conn.execute("DELETE FROM project_compare_alignments WHERE project_id = ?", (project_id,))
    return DEFAULT_ALIGNMENT.copy()
