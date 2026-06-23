"""Read-only delivery preflight checks for a project's final model."""

from __future__ import annotations

import os
from pathlib import Path

from app.repositories import model_artifact_repository


SUPPORTED_FORMATS = {"glb", "obj"}
TEXTURE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tga"}
THUMBNAIL_EXTENSIONS = ("png", "jpg", "jpeg", "webp")
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


def _obj_bundle(path: Path) -> dict:
    """List direct OBJ companion files eligible for delivery packaging."""
    try:
        files = [item for item in path.parent.iterdir() if item.is_file()]
    except OSError:
        files = []
    thumbnail_names = {f"{path.stem}.thumbnail.{extension}" for extension in THUMBNAIL_EXTENSIONS}
    mtl_files = sorted((item.name for item in files if item.suffix.lower() == ".mtl"), key=str.lower)
    texture_files = sorted((item.name for item in files if item.name not in thumbnail_names and item.suffix.lower() in TEXTURE_EXTENSIONS), key=str.lower)
    return {
        "mtlFiles": mtl_files,
        "textureFiles": texture_files,
        "hasMtl": bool(mtl_files),
        "hasTextures": bool(texture_files),
        "supportedForPackaging": True,
    }


def _thumbnail_sidecar(project_id: str, artifact: dict, model_path: Path) -> dict | None:
    """Find one deterministic, direct thumbnail sibling for the active final model."""
    try:
        model_directory = model_path.parent.resolve()
    except OSError:
        return None
    for extension in THUMBNAIL_EXTENSIONS:
        candidate = (model_directory / f"{model_path.stem}.thumbnail.{extension}").resolve()
        if candidate.parent != model_directory or not candidate.is_file():
            continue
        return {
            "exists": True,
            "filename": candidate.name,
            "format": extension,
            "sizeBytes": candidate.stat().st_size,
            "source": "final_model_sidecar",
            "supportedForPackaging": True,
            "fileUrl": f"/projects/{project_id}/model-artifacts/{artifact['artifactId']}/viewer-files/{candidate.name}",
        }
    return None


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
            "bundle": None,
            "thumbnail": None,
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
    bundle = _obj_bundle(path) if model_format == "obj" else None
    thumbnail = _thumbnail_sidecar(project_id, artifact, path) if file_available else None
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

    if model_format == "obj" and bundle:
        message = (
            "OBJ is standalone; no MTL or texture companion files were detected."
            if not bundle["hasMtl"] and not bundle["hasTextures"]
            else None
        )
        if message:
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
        "bundle": bundle,
        "thumbnail": thumbnail,
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "packageReady": package_ready,
    }


def compact_summary(preflight: dict) -> dict:
    """Select the delivery-manifest fields from a full preflight response."""
    final_model = preflight["finalModel"]
    bundle = preflight.get("bundle")
    thumbnail = preflight.get("thumbnail")
    compact_bundle = None if bundle is None else {
        "hasMtl": bundle["hasMtl"],
        "hasTextures": bundle["hasTextures"],
        "mtlFileCount": len(bundle["mtlFiles"]),
        "textureFileCount": len(bundle["textureFiles"]),
        "supportedForPackaging": bundle["supportedForPackaging"],
    }
    compact_thumbnail = None if thumbnail is None else {
        "available": thumbnail["exists"],
        "format": thumbnail["format"],
        "sizeBytes": thumbnail["sizeBytes"],
        "source": thumbnail["source"],
        "supportedForPackaging": thumbnail["supportedForPackaging"],
    }
    return {
        "status": preflight["status"],
        "packageReady": preflight["packageReady"],
        "warnings": preflight["warnings"],
        "blockers": preflight["blockers"],
        "format": final_model["format"],
        "sizeBytes": final_model["sizeBytes"],
        "source": final_model["source"],
        "bundle": compact_bundle,
        "thumbnail": compact_thumbnail,
    }
