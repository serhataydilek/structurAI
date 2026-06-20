from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.database import PROCESSED_DIR

VALID_STATUSES = {"pending", "running", "completed", "failed", "cancelled"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _path(project_id: str, job_key: str) -> Path:
    folder = PROCESSED_DIR / project_id / "job_progress"
    folder.mkdir(parents=True, exist_ok=True)
    safe_key = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in job_key)
    return folder / f"{safe_key}.json"


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _elapsed_seconds(started_at: str | None, finished_at: str | None = None) -> int:
    started = _parse_time(started_at)
    if not started:
        return 0
    end = _parse_time(finished_at) or _now()
    return max(0, int((end - started).total_seconds()))


def _eta_seconds(item: dict[str, Any]) -> int | None:
    processed = item.get("processedItems")
    total = item.get("totalItems")
    progress = item.get("progressPercent")
    if item.get("status") not in {"pending", "running"}:
        return None
    if isinstance(processed, int) and isinstance(total, int) and processed > 0 and total > processed:
        elapsed = _elapsed_seconds(item.get("startedAt"))
        if elapsed <= 0:
            return None
        seconds_per_item = elapsed / processed
        return max(1, int(seconds_per_item * (total - processed)))
    if isinstance(progress, (int, float)) and 0 < progress < 100 and item.get("etaSource") == "historical":
        elapsed = _elapsed_seconds(item.get("startedAt"))
        return max(1, int((elapsed / float(progress)) * (100 - float(progress)))) if elapsed > 0 else None
    return None


def _normalize(item: dict[str, Any]) -> dict[str, Any]:
    finished_at = item.get("finishedAt")
    item["elapsedSeconds"] = _elapsed_seconds(item.get("startedAt"), finished_at)
    item["etaSeconds"] = _eta_seconds(item)
    item.setdefault("progressPercent", None)
    item.setdefault("processedItems", None)
    item.setdefault("totalItems", None)
    item.setdefault("logTail", [])
    item.setdefault("warnings", [])
    item.setdefault("errors", [])
    return item


def start(project_id: str, job_key: str, stage: str, label: str, *, total_items: int | None = None, progress_percent: float | None = 0) -> dict[str, Any]:
    now = _iso()
    item = {
        "jobKey": job_key,
        "projectId": project_id,
        "status": "running",
        "currentStage": stage,
        "currentStepLabel": label,
        "progressPercent": progress_percent,
        "startedAt": now,
        "updatedAt": now,
        "finishedAt": None,
        "elapsedSeconds": 0,
        "etaSeconds": None,
        "processedItems": 0 if total_items is not None else None,
        "totalItems": total_items,
        "logTail": [label],
        "warnings": [],
        "errors": [],
    }
    write(project_id, job_key, item)
    return item


def write(project_id: str, job_key: str, item: dict[str, Any]) -> None:
    _path(project_id, job_key).write_text(json.dumps(_normalize(item), indent=2), encoding="utf-8")


def get(project_id: str, job_key: str) -> dict[str, Any] | None:
    path = _path(project_id, job_key)
    if not path.is_file():
        return None
    try:
        return _normalize(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return None


def update(
    project_id: str,
    job_key: str,
    *,
    stage: str | None = None,
    label: str | None = None,
    progress_percent: float | None = None,
    processed_items: int | None = None,
    total_items: int | None = None,
    log: str | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    item = get(project_id, job_key) or start(project_id, job_key, stage or "pending", label or "Starting", total_items=total_items, progress_percent=progress_percent)
    if item.get("status") == "pending":
        item["status"] = "running"
    if stage is not None:
        item["currentStage"] = stage
    if label is not None:
        item["currentStepLabel"] = label
    if progress_percent is not None:
        item["progressPercent"] = max(0, min(100, round(float(progress_percent), 1)))
    if processed_items is not None:
        item["processedItems"] = processed_items
    if total_items is not None:
        item["totalItems"] = total_items
    if warnings is not None:
        item["warnings"] = warnings
    if errors is not None:
        item["errors"] = errors
    if log or label:
        tail = list(item.get("logTail") or [])
        tail.append(log or label or "")
        item["logTail"] = [entry for entry in tail if entry][-20:]
    item["updatedAt"] = _iso()
    write(project_id, job_key, item)
    return item


def complete(project_id: str, job_key: str, label: str = "Completed", *, warnings: list[str] | None = None) -> dict[str, Any]:
    item = update(project_id, job_key, label=label, progress_percent=100, warnings=warnings)
    item["status"] = "completed"
    item["finishedAt"] = _iso()
    item["updatedAt"] = item["finishedAt"]
    write(project_id, job_key, item)
    return item


def fail(project_id: str, job_key: str, message: str, *, warnings: list[str] | None = None) -> dict[str, Any]:
    item = update(project_id, job_key, label="Failed", errors=[message], warnings=warnings)
    item["status"] = "failed"
    item["finishedAt"] = _iso()
    item["updatedAt"] = item["finishedAt"]
    write(project_id, job_key, item)
    return item

