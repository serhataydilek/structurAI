from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from app.database import get_connection


def _package(row: Any) -> dict[str, Any]:
    item = dict(row)
    return {
        "id": item["package_id"],
        "packageId": item["package_id"],
        "projectId": item["project_id"],
        "version": item["version"],
        "filename": item["filename"],
        "storagePath": item["storage_path"],
        "relativePath": item["relative_path"],
        "sizeBytes": item["size_bytes"],
        "metadata": json.loads(item["metadata_json"] or "{}"),
        "createdAt": item["created_at"],
    }


def create_package(
    project_id: str,
    version: int,
    filename: str,
    storage_path: str,
    relative_path: str,
    size_bytes: int,
    metadata: dict[str, Any],
    *,
    package_id: str | None = None,
) -> dict[str, Any]:
    package_id = package_id or str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO delivery_packages
                (package_id, project_id, version, filename, storage_path, relative_path, size_bytes, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (package_id, project_id, version, filename, storage_path, relative_path, size_bytes, json.dumps(metadata), created_at),
        )
        row = conn.execute("SELECT * FROM delivery_packages WHERE package_id = ?", (package_id,)).fetchone()
    return _package(row)


def get_package(package_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM delivery_packages WHERE package_id = ?", (package_id,)).fetchone()
    return _package(row) if row else None


def get_package_for_project(project_id: str, package_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM delivery_packages WHERE project_id = ? AND package_id = ?",
            (project_id, package_id),
        ).fetchone()
    return _package(row) if row else None


def list_packages(project_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM delivery_packages WHERE project_id = ? ORDER BY version DESC, created_at DESC",
            (project_id,),
        ).fetchall()
    return [_package(row) for row in rows]


def get_latest_package(project_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM delivery_packages WHERE project_id = ? ORDER BY version DESC, created_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()
    return _package(row) if row else None


def get_next_version(project_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM delivery_packages WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    return int(row["next_version"])
