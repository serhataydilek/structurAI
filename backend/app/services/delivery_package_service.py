"""Build and persist immutable delivery package snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import shutil
from uuid import uuid4
import zipfile

from app import database
from app.repositories import delivery_package_repository, model_artifact_repository, project_repository
from app.services import final_model_preflight_service


class DeliveryPackageError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _safe_obj_companion_files(model_path: Path, bundle: dict | None, reserved_archive_names: set[str] | None = None) -> dict:
    result = {"mtlFiles": [], "textureFiles": []}
    if not bundle:
        return result
    companion_root = model_path.parent.resolve()
    archive_names = reserved_archive_names if reserved_archive_names is not None else {"final_model.obj", "delivery-metadata.json"}
    for key in ("mtlFiles", "textureFiles"):
        for file_name in bundle.get(key, []):
            candidate_name = Path(file_name)
            if candidate_name.is_absolute() or candidate_name.name != file_name:
                continue
            candidate = (companion_root / candidate_name).resolve()
            archive_name = candidate.name
            if candidate.parent != companion_root or not candidate.is_file() or archive_name.casefold() in archive_names:
                continue
            archive_names.add(archive_name.casefold())
            result[key].append((archive_name, candidate))
    return result


def _safe_thumbnail_sidecar(model_path: Path, thumbnail: dict | None) -> tuple[str, Path] | None:
    if not thumbnail or thumbnail.get("format") not in {"png", "jpg", "jpeg", "webp"}:
        return None
    file_name = thumbnail.get("filename")
    candidate_name = Path(file_name) if isinstance(file_name, str) else None
    if not candidate_name or candidate_name.is_absolute() or candidate_name.name != file_name:
        return None
    model_directory = model_path.parent.resolve()
    expected_name = f"{model_path.stem}.thumbnail.{thumbnail['format']}"
    candidate = (model_directory / candidate_name).resolve()
    if candidate_name.name != expected_name or candidate.parent != model_directory or not candidate.is_file():
        return None
    return f"final_model_preview.{thumbnail['format']}", candidate


def build_delivery_package(project_id: str, manifest: dict, package_identity: dict | None = None) -> tuple[bytes, dict]:
    """Build the existing delivery ZIP contents without writing them to persistent storage."""
    if not project_repository.get_project(project_id):
        raise DeliveryPackageError(404, "Project not found")
    if not manifest.get("ready"):
        raise DeliveryPackageError(400, "Delivery package is not ready; a final model is required")
    artifact = model_artifact_repository.get_latest_by_artifact_role(project_id, "target_model")
    path = Path(artifact.get("primary_file_path") or artifact["storagePath"]).resolve() if artifact else None
    managed_root = (database.PROCESSED_DIR / project_id / "target_models").resolve()
    if not path or not path.is_file() or managed_root not in path.parents:
        raise DeliveryPackageError(404, "Final model file is unavailable for delivery packaging")
    final_model = manifest.get("metadataPreview", {}).get("finalModel") or {}
    extension = (final_model.get("format") or path.suffix.lstrip(".")).lower()
    if extension not in {"glb", "obj"}:
        raise DeliveryPackageError(400, "Final model format is not supported for delivery packaging")

    preflight = final_model_preflight_service.build_preflight(project_id)
    thumbnail_file = _safe_thumbnail_sidecar(path, preflight.get("thumbnail"))
    reserved_archive_names = {f"final_model.{extension}".casefold(), "delivery-metadata.json"}
    if thumbnail_file:
        reserved_archive_names.add(thumbnail_file[0].casefold())
    companion_files = _safe_obj_companion_files(path, preflight.get("bundle") if extension == "obj" else None, reserved_archive_names)
    obj_bundle = None if extension != "obj" else {
        "included": bool(companion_files["mtlFiles"] or companion_files["textureFiles"]),
        "mtlFiles": [name for name, _ in companion_files["mtlFiles"]],
        "textureFiles": [name for name, _ in companion_files["textureFiles"]],
        "supportedForPackaging": True,
    }
    preview_image = {"included": False} if not thumbnail_file else {
        "included": True,
        "filename": thumbnail_file[0],
        "source": "final_model_sidecar",
        "format": preflight["thumbnail"]["format"],
        "sizeBytes": thumbnail_file[1].stat().st_size,
    }
    metadata = {
        "projectId": project_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "packageVersion": manifest["packageVersion"],
        "finalModel": final_model,
        "manifest": {"ready": manifest["ready"], "missingRequired": manifest["missingRequired"], "items": manifest["metadataPreview"]["items"]},
        "notes": manifest["notes"],
        "objBundle": obj_bundle,
        "previewImage": preview_image,
    }
    if package_identity:
        metadata["package"] = package_identity

    archive = BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.write(path, f"final_model.{extension}")
        for key in ("mtlFiles", "textureFiles"):
            for archive_name, companion_path in companion_files[key]:
                package.write(companion_path, archive_name)
        if thumbnail_file:
            package.write(thumbnail_file[1], thumbnail_file[0])
        package.writestr("delivery-metadata.json", json.dumps(metadata, indent=2))
    return archive.getvalue(), metadata


def generate_persisted_package(project_id: str, manifest: dict) -> dict:
    """Persist a newly generated ZIP snapshot and its metadata record."""
    version = delivery_package_repository.get_next_version(project_id)
    package_id = str(uuid4())
    filename = f"structura-project-{project_id}-delivery-v{version:04d}.zip"
    metadata_identity = {"id": package_id, "version": version}
    archive, metadata = build_delivery_package(project_id, manifest, metadata_identity)
    package_directory = database.PROCESSED_DIR / project_id / "delivery_packages" / package_id
    final_path = package_directory / filename
    temporary_path = package_directory / f"{filename}.tmp"
    try:
        package_directory.mkdir(parents=True, exist_ok=True)
        temporary_path.write_bytes(archive)
        temporary_path.replace(final_path)
        record = delivery_package_repository.create_package(
            project_id,
            version,
            filename,
            str(final_path),
            str(final_path.relative_to(database.PROCESSED_DIR)),
            final_path.stat().st_size,
            metadata,
            package_id=package_id,
        )
    except Exception:
        temporary_path.unlink(missing_ok=True)
        final_path.unlink(missing_ok=True)
        if package_directory.exists():
            shutil.rmtree(package_directory, ignore_errors=True)
        raise
    return record


def package_record_to_api(record: dict) -> dict:
    package_id = record["packageId"]
    project_id = record["projectId"]
    return {
        "id": package_id,
        "projectId": project_id,
        "version": record["version"],
        "filename": record["filename"],
        "sizeBytes": record["sizeBytes"],
        "createdAt": record["createdAt"],
        "downloadUrl": f"/projects/{project_id}/delivery-packages/{package_id}/download",
    }
