"""Render client-facing report artifacts from delivery-package snapshots."""

from __future__ import annotations

from datetime import datetime
import hashlib
import re
from typing import Any


ARTIFACT_FILENAME = "report.md"
ARTIFACT_CONTENT_TYPE = "text/markdown; charset=utf-8"


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _values(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _text(value: object, default: str = "Not available") -> str:
    if value is None:
        return default
    normalized = re.sub(r"\s+", " ", str(value).replace("\r\n", "\n").replace("\r", "\n")).strip()
    if not normalized:
        return default
    escaped = re.sub(r"([\\`*_{}\[\]()<>#+!|])", r"\\\1", normalized)
    return re.sub(r"^(-|\+|\d+\.)\s", r"\\\1 ", escaped)


def _filename(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip() or "://" in value:
        return None
    name = value.replace("\\", "/").rsplit("/", 1)[-1]
    return _text(name) if name else None


def _size(value: object) -> str | None:
    return f"{value} bytes" if isinstance(value, int) and value >= 0 else None


def _append_list(lines: list[str], values: object) -> None:
    for value in values if isinstance(values, list) else []:
        lines.append(f"- {_text(value)}")


def build_report_markdown(
    report: dict,
    manifest: dict,
    package_identity: dict,
    generated_at: datetime,
) -> tuple[bytes, dict]:
    """Return a deterministic Markdown delivery-report artifact and its metadata.

    The renderer deliberately uses only a small allowlist of report and manifest fields.
    This prevents server paths, job logs, and API download URLs from being copied into
    a client-facing delivery artifact.
    """
    report = _mapping(report)
    manifest = _mapping(manifest)
    package_identity = _mapping(package_identity)
    capture = _mapping(report.get("captureMetadata"))
    reconstruction = _mapping(report.get("reconstructionMetadata"))
    metadata_preview = _mapping(manifest.get("metadataPreview"))
    final_model = _mapping(metadata_preview.get("finalModel"))
    quality = _mapping(manifest.get("finalModelQuality"))

    project_name = _text(report.get("projectName") or manifest.get("projectName") or "Project report")
    project_id = _text(report.get("projectId") or manifest.get("projectId"))
    generated = generated_at.isoformat()
    package_id = _text(package_identity.get("id"), "Not assigned")
    package_version = _text(package_identity.get("version"), "Not assigned")
    package_filename = _filename(package_identity.get("filename"))

    lines = [
        f"# Delivery Report: {project_name}",
        "",
        "## Package Snapshot",
        "",
        f"- Project ID: {project_id}",
        f"- Package ID: {package_id}",
        f"- Package version: {package_version}",
        f"- Generated at: {generated}",
    ]
    if package_filename:
        lines.append(f"- Package filename: {package_filename}")

    lines.extend(["", "## Delivery Readiness", "", f"- Ready: {_text(manifest.get('ready'), 'Unknown')}"])
    missing_required = _values(manifest.get("missingRequired"))
    if missing_required:
        lines.append("- Missing required items:")
        _append_list(lines, missing_required)
    else:
        lines.append("- Missing required items: None")

    lines.extend(["", "### Delivery Items", ""])
    for item in _items(manifest.get("items")):
        details = [
            f"ready: {_text(item.get('ready'), 'Unknown')}",
            f"required: {_text(item.get('required'), 'Unknown')}",
        ]
        filename = _filename(item.get("filename"))
        if filename:
            details.append(f"filename: {filename}")
        if item.get("format") is not None:
            details.append(f"format: {_text(item.get('format'))}")
        size = _size(item.get("sizeBytes"))
        if size:
            details.append(f"size: {size}")
        lines.append(f"- {_text(item.get('kind'), 'item')} ({'; '.join(details)})")
    if not _items(manifest.get("items")):
        lines.append("- No delivery items available.")

    lines.extend(["", "## Final Model", ""])
    if final_model:
        for label, key in (("Filename", "filename"), ("Format", "format"), ("Source", "source"), ("Created at", "createdAt")):
            value = _filename(final_model.get(key)) if key == "filename" else _text(final_model.get(key))
            if value and value != "Not available":
                lines.append(f"- {label}: {value}")
        size = _size(final_model.get("sizeBytes"))
        if size:
            lines.append(f"- Size: {size}")
    else:
        lines.append("- No final model is available.")

    if quality:
        lines.extend(["", "### Final Model Quality", "", f"- Status: {_text(quality.get('status'), 'Unknown')}"])
        if quality.get("packageReady") is not None:
            lines.append(f"- Package ready: {_text(quality.get('packageReady'))}")
        for heading, key in (("Warnings", "warnings"), ("Blockers", "blockers")):
            values = quality.get(key)
            if isinstance(values, list) and values:
                lines.extend(["", f"#### {heading}", ""])
                _append_list(lines, values)

    lines.extend(["", "## Report Summary", ""])
    for label, value in (
        ("Processing status", report.get("processingStatus")),
        ("Detected output", report.get("detectedOutput")),
        ("Uploaded media", report.get("uploadedMediaCount")),
        ("Capture images", capture.get("imageCount")),
        ("Capture videos", capture.get("videoCount")),
        ("Extracted frames", capture.get("extractedFrameCount")),
        ("Reconstruction status", reconstruction.get("status")),
        ("Sparse quality", reconstruction.get("sparseQualityLabel")),
        ("Registered images", reconstruction.get("registeredImageCount")),
        ("Sparse points", reconstruction.get("sparsePointCount")),
    ):
        if value is not None:
            lines.append(f"- {label}: {_text(value)}")

    annotations = _items(report.get("annotations"))
    if annotations:
        lines.extend(["", "## Annotations", ""])
        for annotation in annotations:
            lines.append(f"- {_text(annotation.get('text'))}")

    notes = _values(manifest.get("notes")) + _values(report.get("limitations"))
    if notes:
        lines.extend(["", "## Notes and Limitations", ""])
        _append_list(lines, notes)

    markdown = "\n".join(lines).replace("\r\n", "\n").replace("\r", "\n").rstrip() + "\n"
    content = markdown.encode("utf-8")
    return content, {
        "filename": ARTIFACT_FILENAME,
        "format": "md",
        "contentType": ARTIFACT_CONTENT_TYPE,
        "sizeBytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
