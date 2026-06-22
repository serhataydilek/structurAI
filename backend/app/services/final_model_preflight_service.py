"""Read-only delivery preflight checks for a project's final model."""

from __future__ import annotations

import os
from pathlib import Path

from app.repositories import model_artifact_repository


SUPPORTED_FORMATS = {"glb", "obj"}
DEFAULT_LARGE_MODEL_MB = 250


def _large_model_threshold_bytes() -> int:
    """Use the existing preview-size setting unless a preflight-specific one is set."""
    raw_value = os.getenv("STRUCTURA_FINAL_MODEL_LARGE_MB") or os.getenv("STRUCTURA_PREVIEW_MAX_GLB_MB")
    try:
        megabytes = int(raw_value) if raw_value else DEFAULT_LARGE_MODEL_MB
    except ValueError:
        megabytes = DEFAULT_LARGE_MODEL_MB
    return max(megabytes, 0) * 1024 * 1024


def _source(artifact: dict) -> str:
    if artifact.get("sourceArtifactId"):
        return "promoted"
    metadata = artifact.get("metadata") or {}
    source = metadata.get("finalModelSource") or metadata.get("source")
    return source if isinstance(source, str) and source else "uploaded"


def _check(key: str, label: str, status: str, message: str) -> dict:
    return {"key": key, "label": label, "status": status, "message": message}


def build_preflight(project_id: str) -> dict:
    """Return a stable, non-persistent readiness summary for the final model."""
    artifact = model_artifact_repository.get_latest_by_artifact_role(project_id, "target_model")
    if not artifact:
        message = "No target model has been uploaded or promoted yet."
        checks = [
            _check("final_model_exists", "Final model exists", "fail", message),
            _check("format_supported", "Final model format is supported", "fail", "A final model is required before its format can be validated."),
            _check("delivery_metadata_generatable", "Delivery metadata can be generated", "pass", "delivery-metadata.json is generated when the delivery ZIP is requested."),
            _check("package_downloadable", "Delivery package can be downloaded", "fail", "A final model is required before the delivery package can be downloaded."),
        ]
        return {
            "projectId": project_id,
            "status": "missing",
            "finalModel": {"exists": False, "artifactId": None, "filename": None, "format": None, "sizeBytes": None, "source": "unknown"},
            "checks": checks,
            "warnings": [],
            "blockers": [message],
            "packageReady": False,
        }

    path = Path(artifact.get("primary_file_path") or artifact["storagePath"])
    file_available = path.is_file()
    model_format = (artifact.get("format") or path.suffix.lstrip(".")).lower()
    supported = model_format in SUPPORTED_FORMATS
    size_bytes = artifact.get("fileSize")
    source = _source(artifact)
    warnings: list[str] = []
    blockers: list[str] = []
    checks = []

    if file_available:
        checks.append(_check("final_model_exists", "Final model exists", "pass", "Final model artifact is available."))
    else:
        message = "Final model artifact file is unavailable."
        checks.append(_check("final_model_exists", "Final model exists", "fail", message))
        blockers.append(message)

    if supported:
        checks.append(_check("format_supported", "Final model format is supported", "pass", f".{model_format} is supported for delivery packaging."))
    else:
        message = f".{model_format or 'unknown'} is not supported for delivery packaging; use .glb or .obj."
        checks.append(_check("format_supported", "Final model format is supported", "fail", message))
        blockers.append(message)

    checks.append(_check("delivery_metadata_generatable", "Delivery metadata can be generated", "pass", "delivery-metadata.json is generated when the delivery ZIP is requested."))

    if isinstance(size_bytes, int) and size_bytes > _large_model_threshold_bytes():
        message = "Final model file is large and may take longer to download."
        checks.append(_check("file_size", "Final model file size", "warning", message))
        warnings.append(message)
    else:
        checks.append(_check("file_size", "Final model file size", "pass", "Final model file size is within the configured preflight threshold."))

    if model_format == "obj" and not artifact.get("mtl_file_path") and not artifact.get("texture_dir_path"):
        message = "OBJ is standalone; MTL and texture bundle files are not included in delivery packaging."
        checks.append(_check("obj_bundle_support", "OBJ material and texture bundle support", "warning", message))
        warnings.append(message)

    package_ready = file_available and supported
    if package_ready:
        checks.append(_check("package_downloadable", "Delivery package can be downloaded", "pass", "Final model and delivery metadata can be packaged for download."))
    else:
        checks.append(_check("package_downloadable", "Delivery package can be downloaded", "fail", "Resolve final model blockers before downloading the delivery package."))

    return {
        "projectId": project_id,
        "status": "blocked" if blockers else "warning" if warnings else "ready",
        "finalModel": {
            "exists": file_available,
            "artifactId": artifact["artifactId"],
            "filename": artifact["fileName"],
            "format": model_format if supported else "unsupported",
            "sizeBytes": size_bytes,
            "source": source,
        },
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "packageReady": package_ready,
    }


def compact_summary(preflight: dict) -> dict:
    """Select the delivery-manifest fields from a full preflight response."""
    final_model = preflight["finalModel"]
    return {
        "status": preflight["status"],
        "packageReady": preflight["packageReady"],
        "warnings": preflight["warnings"],
        "blockers": preflight["blockers"],
        "format": final_model["format"],
        "sizeBytes": final_model["sizeBytes"],
        "source": final_model["source"],
    }
