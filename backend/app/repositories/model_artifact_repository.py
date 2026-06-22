from datetime import datetime, timezone
import json
from uuid import uuid4

from app.database import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_type(source_tool: str) -> str:
    if source_tool == "realityscan":
        return "realityscan"
    if source_tool == "colmap":
        return "colmap"
    return "imported"


def _artifact(row) -> dict:
    item = dict(row)
    item["stats"] = json.loads(item.pop("stats_json") or "{}")
    item["bundle"] = json.loads(item.pop("bundle_json", "{}") or "{}")
    metadata = json.loads(item.pop("metadata_json", "{}") or "{}")
    artifact_id = item.pop("artifact_id")
    project_id = item.pop("project_id")
    artifact_type = item.pop("artifact_type")
    source_tool = item.pop("source_tool")
    storage_path = item.pop("storage_path")
    created_at = item.pop("created_at")
    updated_at = item.pop("updated_at")
    return {
        "id": artifact_id, "artifactId": artifact_id, "projectId": project_id,
        "project_id": project_id, "artifactType": artifact_type, "artifact_type": artifact_type, "sourceTool": source_tool,
        "fileName": item.pop("file_name"), "fileSize": item.pop("file_size"),
        "storagePath": storage_path, "relativePath": item.pop("relative_path"),
        "notes": item.pop("notes"), "role": item.pop("role"), "stats": item.pop("stats"), "bundle": item.pop("bundle"),
        "source_type": item.pop("source_type", None) or _source_type(source_tool), "job_id": item.pop("job_id", None),
        "format": item.pop("format", None), "primary_file_path": item.pop("primary_file_path", None) or storage_path,
        "mtl_file_path": item.pop("mtl_file_path", None), "texture_dir_path": item.pop("texture_dir_path", None),
        "status": item.pop("status", "ready") or "ready", "metadata": metadata,
        "artifactRole": item.pop("artifact_role", "raw_realityscan") or "raw_realityscan",
        "sourceArtifactId": item.pop("source_artifact_id", None), "sourceJobId": item.pop("source_job_id", None),
        "createdAt": created_at, "created_at": created_at, "updatedAt": updated_at,
    }


def add_artifact(project_id: str, artifact_type: str, source_tool: str, file_name: str, file_size: int,
                 storage_path: str, relative_path: str, notes: str, role: str | None, stats: dict, bundle: dict | None = None,
                 *, source_type: str | None = None, job_id: str | None = None, model_format: str | None = None,
                 primary_file_path: str | None = None, mtl_file_path: str | None = None, texture_dir_path: str | None = None,
                 status: str = "ready", metadata: dict | None = None) -> dict:
    artifact_id, now = str(uuid4()), _now()
    source_type = source_type or _source_type(source_tool)
    primary_file_path = primary_file_path or storage_path
    with get_connection() as conn:
        conn.execute("""INSERT INTO model_artifacts
            (artifact_id, project_id, artifact_type, source_tool, file_name, file_size, storage_path, relative_path, notes, role, stats_json, bundle_json, source_type, job_id, format, primary_file_path, mtl_file_path, texture_dir_path, status, metadata_json, artifact_role, source_artifact_id, source_job_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (artifact_id, project_id, artifact_type, source_tool, file_name, file_size, storage_path,
             relative_path, notes, role, json.dumps(stats), json.dumps(bundle or {}), source_type, job_id, model_format,
             primary_file_path, mtl_file_path, texture_dir_path, status, json.dumps(metadata or {}),
             (metadata or {}).get("artifactRole", "raw_realityscan"), (metadata or {}).get("sourceArtifactId"), (metadata or {}).get("sourceJobId"), now, now))
        row = conn.execute("SELECT * FROM model_artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
    return _artifact(row)


def list_artifacts(project_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM model_artifacts WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
    return [_artifact(row) for row in rows]


def get_artifact(project_id: str, artifact_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM model_artifacts WHERE project_id = ? AND artifact_id = ?", (project_id, artifact_id)).fetchone()
    return _artifact(row) if row else None


def get_latest_ready_artifact(project_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM model_artifacts WHERE project_id = ? AND status = 'ready' AND artifact_role != 'target_model' ORDER BY CASE artifact_role WHEN 'viewer_ready' THEN 0 WHEN 'cleaned_mesh' THEN 1 WHEN 'raw_realityscan' THEN 2 ELSE 3 END, created_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()
    return _artifact(row) if row else None


def get_latest_by_artifact_role(project_id: str, artifact_role: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM model_artifacts WHERE project_id = ? AND artifact_role = ? AND status = 'ready' ORDER BY created_at DESC LIMIT 1",
            (project_id, artifact_role),
        ).fetchone()
    return _artifact(row) if row else None


def supersede_ready_artifacts_by_role(project_id: str, artifact_role: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE model_artifacts SET status = 'superseded', updated_at = ? WHERE project_id = ? AND artifact_role = ? AND status = 'ready'",
            (_now(), project_id, artifact_role),
        )


def delete_artifact(project_id: str, artifact_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM model_artifacts WHERE project_id = ? AND artifact_id = ?", (project_id, artifact_id))
    return cursor.rowcount > 0


def set_role(project_id: str, artifact_id: str, role: str | None) -> dict | None:
    with get_connection() as conn:
        conn.execute("UPDATE model_artifacts SET role = ?, updated_at = ? WHERE project_id = ? AND artifact_id = ?", (role, _now(), project_id, artifact_id))
    return get_artifact(project_id, artifact_id)


def add_comparison(project_id: str, reference_artifact_id: str, current_artifact_id: str, status: str, notes: str, analysis: dict | None = None) -> dict:
    comparison_id, now = str(uuid4()), _now()
    analysis = analysis or {}
    with get_connection() as conn:
        conn.execute("""INSERT INTO artifact_comparisons (comparison_id,project_id,reference_artifact_id,current_artifact_id,status,notes,created_at,updated_at,analysis_status,analysis_summary_json,warnings_json,reference_bounds_json,current_bounds_json,rough_bounds_delta_json,scale_mismatch_warning,no_progress_percentage_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (comparison_id, project_id, reference_artifact_id, current_artifact_id, status, notes, now, now, analysis.get("analysisStatus","not_started"), json.dumps(analysis.get("analysisSummary",{})), json.dumps(analysis.get("warnings",[])), json.dumps(analysis.get("referenceBounds")), json.dumps(analysis.get("currentBounds")), json.dumps(analysis.get("roughBoundsDelta")), analysis.get("scaleMismatchWarning"), analysis.get("noProgressPercentageReason")))
    return get_comparison(project_id, comparison_id)


def get_comparison(project_id: str, comparison_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM artifact_comparisons WHERE project_id = ? AND comparison_id = ?", (project_id, comparison_id)).fetchone()
    if not row:
        return None
    item = dict(row)
    return {"comparisonId": item["comparison_id"], "projectId": item["project_id"], "referenceArtifactId": item["reference_artifact_id"],
            "currentArtifactId": item["current_artifact_id"], "status": item["status"], "notes": item["notes"],
            "createdAt": item["created_at"], "updatedAt": item["updated_at"], "analysisStatus": item.get("analysis_status","not_started"), "analysisSummary": json.loads(item.get("analysis_summary_json") or "{}"), "warnings": json.loads(item.get("warnings_json") or "[]"), "referenceBounds": json.loads(item.get("reference_bounds_json") or "null"), "currentBounds": json.loads(item.get("current_bounds_json") or "null"), "roughBoundsDelta": json.loads(item.get("rough_bounds_delta_json") or "null"), "scaleMismatchWarning":item.get("scale_mismatch_warning"), "noProgressPercentageReason":item.get("no_progress_percentage_reason")}


def list_comparisons(project_id: str) -> list[dict]:
    with get_connection() as conn:
        ids = conn.execute("SELECT comparison_id FROM artifact_comparisons WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
    return [get_comparison(project_id, row["comparison_id"]) for row in ids]
