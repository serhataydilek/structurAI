from pathlib import Path
import shutil
from uuid import uuid4

from app.database import PROCESSED_DIR
from app.repositories import model_artifact_repository

ALLOWED_EXTENSIONS = {".ply", ".obj"}
ARTIFACT_TYPES = {"dense_point_cloud", "textured_mesh", "mesh", "gaussian_splat", "unknown"}
SOURCE_TOOLS = {"realitycapture", "metashape", "pix4d", "cloudcompare", "manual", "unknown"}
ROLES = {"current_state", "finished_reference", "baseline", "comparison_result"}


class ModelArtifactError(Exception):
    pass


def _number(value: str):
    return float(value)


def _bounds(vertices: list[tuple[float, float, float]]) -> dict | None:
    if not vertices:
        return None
    xs, ys, zs = zip(*vertices)
    return {"min": {"x": min(xs), "y": min(ys), "z": min(zs)}, "max": {"x": max(xs), "y": max(ys), "z": max(zs)}}


def _ply_header(path: Path) -> dict:
    """Read only the PLY header so binary files remain safe to import."""
    with path.open("rb") as raw:
        lines: list[str] = []
        for _ in range(300):
            line = raw.readline()
            if not line:
                break
            decoded = line.decode("ascii", errors="ignore").strip()
            lines.append(decoded)
            if decoded == "end_header":
                break
    if not lines or lines[0] != "ply" or lines[-1] != "end_header":
        return {}
    vertex_count: int | None = None
    face_count: int | None = None
    properties: list[str] = []
    in_vertex = False
    for line in lines:
        parts = line.split()
        if parts[:2] == ["element", "vertex"]:
            vertex_count, in_vertex = int(parts[2]), True
        elif parts[:2] == ["element", "face"]:
            face_count, in_vertex = int(parts[2]), False
        elif in_vertex and parts[:1] == ["property"]:
            properties.append(parts[-1].lower())
    gaussian_markers = ("opacity", "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3", "f_dc", "f_rest")
    return {
        "format": next((line for line in lines if line.startswith("format ")), ""),
        "vertexCount": vertex_count,
        "faceCount": face_count,
        "properties": properties,
        "gaussianSplatDetected": any(name == marker or name.startswith(f"{marker}_") for name in properties for marker in gaussian_markers),
        "hasColor": any(name in properties for name in ("red", "green", "blue", "r", "g", "b")),
    }


def _parse_ascii_ply(path: Path) -> dict:
    # Deliberately bounded: headers and the first 250k vertices are enough for quick import metadata.
    with path.open("rb") as raw:
        header = []
        for _ in range(200):
            line = raw.readline()
            if not line:
                break
            decoded = line.decode("ascii", errors="ignore").strip()
            header.append(decoded)
            if decoded == "end_header":
                break
        if not header or header[0] != "ply" or "format ascii" not in " ".join(header):
            return {}
        vertex_count = 0
        face_count: int | None = None
        properties: list[str] = []
        in_vertex = False
        for line in header:
            parts = line.split()
            if parts[:2] == ["element", "vertex"]:
                vertex_count, in_vertex = int(parts[2]), True
            elif parts[:2] == ["element", "face"]:
                face_count, in_vertex = int(parts[2]), False
            elif in_vertex and parts[:1] == ["property"]:
                properties.append(parts[-1].lower())
        positions = {name: properties.index(name) for name in ("x", "y", "z") if name in properties}
        vertices = []
        for _ in range(min(vertex_count, 250000)):
            parts = raw.readline().decode("ascii", errors="ignore").split()
            if len(positions) == 3 and len(parts) > max(positions.values()):
                try:
                    vertices.append(tuple(_number(parts[positions[k]]) for k in ("x", "y", "z")))
                except ValueError:
                    pass
        return {"vertexCount": vertex_count, "faceCount": face_count, "boundingBox": _bounds(vertices),
                "hasColor": any(name in properties for name in ("red", "green", "blue", "r", "g", "b")), "statsPartial": vertex_count > 250000}


def _parse_obj(path: Path) -> dict:
    vertices, faces, has_color = [], 0, False
    with path.open("r", encoding="utf-8", errors="ignore") as file:
        for index, line in enumerate(file):
            if index > 500000:
                break
            if line.startswith("v "):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
                        has_color = has_color or len(parts) >= 7
                    except ValueError:
                        pass
            elif line.startswith("f "):
                faces += 1
    return {"vertexCount": len(vertices), "faceCount": faces, "boundingBox": _bounds(vertices), "hasColor": has_color,
            "statsPartial": path.stat().st_size > 100 * 1024 * 1024}


def parse_stats(path: Path) -> dict:
    try:
        if path.suffix.lower() != ".ply":
            return _parse_obj(path)
        header = _ply_header(path)
        if not header:
            return {}
        if "format ascii" in header["format"]:
            return {**header, **_parse_ascii_ply(path)}
        # Binary PLY statistics are header-only: do not scan potentially huge vertex payloads.
        return {key: value for key, value in header.items() if key != "properties"} | {"boundingBox": None, "statsPartial": True}
    except OSError:
        return {}


def _is_gaussian_splat(artifact: dict) -> bool:
    if artifact["artifactType"] == "gaussian_splat":
        return True
    stats = artifact.get("stats") or {}
    if stats.get("gaussianSplatDetected"):
        return True
    path = Path(artifact["storagePath"])
    if path.suffix.lower() == ".ply" and path.is_file():
        detected = bool(_ply_header(path).get("gaussianSplatDetected"))
        if detected:
            stats["gaussianSplatDetected"] = True
            artifact["stats"] = stats
        return detected
    return False


def import_artifact(project_id: str, source_path: Path, original_name: str, artifact_type: str, source_tool: str, notes: str, role: str | None) -> dict:
    if artifact_type not in ARTIFACT_TYPES or source_tool not in SOURCE_TOOLS or (role and role not in ROLES):
        raise ModelArtifactError("Unsupported artifact type, source tool, or role")
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ModelArtifactError("Only .ply and .obj model artifacts are supported")
    if not source_path.is_file():
        raise ModelArtifactError("Artifact file was not found")
    target_dir = PROCESSED_DIR / project_id / "model_artifacts"
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(original_name).name
    target = target_dir / f"{uuid4()}_{safe_name}"
    shutil.copyfile(source_path, target)
    return model_artifact_repository.add_artifact(project_id, artifact_type, source_tool, safe_name, target.stat().st_size,
        str(target), str(target.relative_to(PROCESSED_DIR)), notes, role, parse_stats(target))


def summary(project_id: str) -> dict:
    artifacts = model_artifact_repository.list_artifacts(project_id)
    for artifact in artifacts:
        if _is_gaussian_splat(artifact) and artifact["artifactType"] != "gaussian_splat":
            artifact["importWarning"] = "Gaussian Splat header detected. Preview-only. Not measurement-grade; do not use as finished/current progress comparison input."
    latest = lambda predicate: next((item for item in artifacts if predicate(item)), None)
    reference = latest(lambda item: item["role"] == "finished_reference")
    current = latest(lambda item: item["role"] == "current_state")
    return {"artifacts": artifacts, "latestDensePointCloud": latest(lambda item: item["artifactType"] == "dense_point_cloud"),
            "latestMesh": latest(lambda item: item["artifactType"] in {"mesh", "textured_mesh"}), "latestReferenceModel": reference,
            "latestCurrentStateModel": current, "comparisonReady": bool(reference and current),
            "message": "Comparison foundation ready" if reference and current else "Import and mark a finished reference and current-state model to prepare comparison."}


def comparison_detail(project_id: str, comparison: dict) -> dict:
    reference = model_artifact_repository.get_artifact(project_id, comparison["referenceArtifactId"])
    current = model_artifact_repository.get_artifact(project_id, comparison["currentArtifactId"])
    if not reference or not current:
        raise ModelArtifactError("Comparison artifacts are missing")
    has_gaussian_splat = _is_gaussian_splat(reference) or _is_gaussian_splat(current)
    comparable = not has_gaussian_splat
    return {**comparison, "referenceArtifact": reference, "currentArtifact": current, "comparable": comparable,
            "warning": None if comparable else "This comparison is a workflow placeholder only. Use dense point clouds or meshes for real progress measurement.",
            "recommendation": "External alignment/distance analysis required. Internal point cloud distance engine pending."}
