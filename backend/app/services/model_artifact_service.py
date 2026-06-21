from pathlib import Path
import os
import shutil
from pathlib import PurePosixPath
from uuid import uuid4
import zipfile

from app.database import PROCESSED_DIR
from app.repositories import model_artifact_repository
from app.services import job_progress_service

ALLOWED_EXTENSIONS = {".ply", ".obj", ".zip"}
ZIP_ALLOWED_EXTENSIONS = {".obj", ".mtl", ".jpg", ".jpeg", ".png", ".webp", ".rsinfo"}
TEXTURE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
ARTIFACT_TYPES = {"dense_point_cloud", "textured_mesh", "mesh", "gaussian_splat", "unknown"}
SOURCE_TOOLS = {"realitycapture", "realityscan", "metashape", "pix4d", "cloudcompare", "manual", "unknown"}
ROLES = {"current_state", "finished_reference", "baseline", "comparison_result"}
JOB_KEY = "model_artifact_import"
DEFAULT_MAX_GLB_MB = 250
DEFAULT_MAX_FACES_FOR_VIEWER = 500_000


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
    vertex_count, faces, has_color = 0, 0, False
    minimum = [float("inf"), float("inf"), float("inf")]
    maximum = [float("-inf"), float("-inf"), float("-inf")]
    with path.open("r", encoding="utf-8", errors="ignore") as file:
        for line in file:
            if line.startswith("v "):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        coordinates = (float(parts[1]), float(parts[2]), float(parts[3]))
                        vertex_count += 1
                        for index, value in enumerate(coordinates):
                            minimum[index] = min(minimum[index], value)
                            maximum[index] = max(maximum[index], value)
                        has_color = has_color or len(parts) >= 7
                    except ValueError:
                        pass
            elif line.startswith("f "):
                faces += 1
    bounding_box = None if vertex_count == 0 else {"min": {"x": minimum[0], "y": minimum[1], "z": minimum[2]}, "max": {"x": maximum[0], "y": maximum[1], "z": maximum[2]}}
    return {"vertexCount": vertex_count, "faceCount": faces, "boundingBox": bounding_box, "hasColor": has_color, "statsPartial": False}


def _safe_zip_member(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    member = PurePosixPath(normalized)
    if member.is_absolute() or ".." in member.parts or not member.parts:
        raise ModelArtifactError("ZIP contains an unsafe path")
    return member


def _import_obj_bundle(project_id: str, source_path: Path, original_name: str, artifact_type: str, source_tool: str,
                       notes: str, role: str | None) -> dict:
    if artifact_type != "textured_mesh":
        raise ModelArtifactError("ZIP bundles are supported only for textured_mesh artifacts")
    try:
        job_progress_service.update(project_id, JOB_KEY, stage="validating_zip", label="Validating OBJ/MTL/texture ZIP", progress_percent=15)
        with zipfile.ZipFile(source_path) as archive:
            members = [info for info in archive.infolist() if not info.is_dir()]
            if len(members) > 5000:
                raise ModelArtifactError("ZIP contains too many files")
            total_size = sum(info.file_size for info in members)
            if total_size > 8 * 1024 * 1024 * 1024:
                raise ModelArtifactError("ZIP uncompressed size exceeds the 8 GB import limit")
            validated: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
            for info in members:
                member = _safe_zip_member(info.filename)
                if member.suffix.lower() not in ZIP_ALLOWED_EXTENSIONS:
                    raise ModelArtifactError(f"ZIP contains unsupported file: {member.name}")
                validated.append((info, member))
            obj_members = [(info, member) for info, member in validated if member.suffix.lower() == ".obj"]
            if not obj_members:
                raise ModelArtifactError("Textured mesh ZIP must contain an .obj file")
            root = PROCESSED_DIR / project_id / "model_artifacts" / f"bundle_{uuid4()}"
            root.mkdir(parents=True, exist_ok=True)
            zip_target = root / Path(original_name).name
            job_progress_service.update(project_id, JOB_KEY, stage="storing_source_zip", label="Storing source ZIP", progress_percent=25)
            shutil.copyfile(source_path, zip_target)
            extracted = root / "contents"
            job_progress_service.update(project_id, JOB_KEY, stage="extracting_bundle", label=f"Extracting bundle files: 0/{len(validated)}", progress_percent=30, processed_items=0, total_items=len(validated))
            for index, (info, member) in enumerate(validated, start=1):
                target = extracted.joinpath(*member.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, target.open("wb") as dest:
                    shutil.copyfileobj(src, dest, length=1024 * 1024)
                if index == len(validated) or index % 10 == 0:
                    job_progress_service.update(project_id, JOB_KEY, label=f"Extracted file {index}/{len(validated)}", progress_percent=30 + index / max(len(validated), 1) * 40, processed_items=index, total_items=len(validated))
    except zipfile.BadZipFile as exc:
        raise ModelArtifactError("Uploaded ZIP is invalid") from exc
    main_info, main_member = max(obj_members, key=lambda item: item[0].file_size)
    job_progress_service.update(project_id, JOB_KEY, stage="locating_model_files", label="Locating main OBJ, MTL, and textures", progress_percent=75, processed_items=None, total_items=None)
    main_obj = extracted.joinpath(*main_member.parts)
    mtl_members = [member for _, member in validated if member.suffix.lower() == ".mtl"]
    textures = [member for _, member in validated if member.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    bundle = {
        "originalZipPath": str(zip_target), "bundleRootPath": str(extracted), "mainObjPath": str(main_obj),
        "mtlPath": str(extracted.joinpath(*mtl_members[0].parts)) if mtl_members else None,
        "textureFiles": [str(member) for member in textures], "textureCount": len(textures), "mtlFound": bool(mtl_members),
    }
    job_progress_service.update(project_id, JOB_KEY, stage="parsing_obj_metadata", label="Parsing OBJ metadata", progress_percent=85)
    stats = _parse_obj(main_obj)
    job_progress_service.update(project_id, JOB_KEY, stage="storing_artifact_record", label="Storing artifact record", progress_percent=95)
    artifact = model_artifact_repository.add_artifact(project_id, artifact_type, source_tool, Path(original_name).name, zip_target.stat().st_size,
        str(zip_target), str(zip_target.relative_to(PROCESSED_DIR)), notes, role, stats, bundle)
    job_progress_service.complete(project_id, JOB_KEY, "Model artifact import complete")
    return artifact


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


def _related_mtl_path(model_path: Path) -> Path | None:
    try:
        for line in model_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.lower().startswith("mtllib "):
                candidate = model_path.parent / line.split(maxsplit=1)[1].strip()
                if candidate.is_file():
                    return candidate
    except OSError:
        return None
    same_name = model_path.with_suffix(".mtl")
    if same_name.is_file():
        return same_name
    return next((path for path in model_path.parent.glob("*.mtl") if path.is_file()), None)


def register_realityscan_export(project_id: str, job_id: str, exported_model_path: Path) -> dict:
    if not exported_model_path.is_file() or exported_model_path.suffix.lower() != ".obj":
        raise ModelArtifactError("RealityScan OBJ export was not found")

    mtl_path = _related_mtl_path(exported_model_path)
    texture_files = [path for path in exported_model_path.parent.rglob("*") if path.is_file() and path.suffix.lower() in TEXTURE_EXTENSIONS]
    texture_dir_path = None
    if texture_files:
        texture_dir_path = str(texture_files[0].parent if len({path.parent for path in texture_files}) == 1 else exported_model_path.parent)
    bundle = {
        "mainObjPath": str(exported_model_path),
        "mtlPath": str(mtl_path) if mtl_path else None,
        "mtlFound": bool(mtl_path),
        "textureFiles": [str(path) for path in texture_files],
        "textureCount": len(texture_files),
    }
    return model_artifact_repository.add_artifact(
        project_id,
        "textured_mesh",
        "realityscan",
        exported_model_path.name,
        exported_model_path.stat().st_size,
        str(exported_model_path),
        str(exported_model_path),
        "RealityScan exported OBJ",
        "current_state",
        parse_stats(exported_model_path),
        bundle,
        source_type="realityscan",
        job_id=job_id,
        model_format="obj",
        primary_file_path=str(exported_model_path),
        mtl_file_path=str(mtl_path) if mtl_path else None,
        texture_dir_path=texture_dir_path,
        status="ready",
        metadata={"textureCount": len(texture_files), "mtlFound": bool(mtl_path), "artifactRole": "raw_realityscan", "sourceJobId": job_id},
    )


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


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _viewer_ready_for_browser(artifact: dict) -> bool:
    if artifact.get("artifactRole") != "viewer_ready":
        return False
    model_format = (artifact.get("format") or Path((artifact.get("bundle") or {}).get("mainGlbPath") or artifact["storagePath"]).suffix.lstrip(".")).lower()
    if model_format not in {"glb", "gltf"} or artifact.get("status") != "ready":
        return False
    max_bytes = _int_env("STRUCTURA_PREVIEW_MAX_GLB_MB", DEFAULT_MAX_GLB_MB) * 1024 * 1024
    max_faces = _int_env("STRUCTURA_PREVIEW_MAX_FACES_FOR_VIEWER", DEFAULT_MAX_FACES_FOR_VIEWER)
    face_count = (artifact.get("stats") or {}).get("faceCount")
    return artifact.get("fileSize", 0) <= max_bytes and isinstance(face_count, int | float) and face_count <= max_faces


def comparison_candidate(artifact: dict) -> dict:
    model_path = Path((artifact.get("bundle") or {}).get("mainObjPath") or artifact["storagePath"])
    preview = _is_gaussian_splat(artifact)
    measurement = artifact["artifactType"] in {"dense_point_cloud", "mesh", "textured_mesh"} and not preview and model_path.is_file()
    return {"artifactId":artifact["artifactId"],"artifactType":artifact["artifactType"],"sourceTool":artifact["sourceTool"],"role":artifact["role"],"vertexCount":(artifact.get("stats") or {}).get("vertexCount"),"faceCount":(artifact.get("stats") or {}).get("faceCount"),"bounds":(artifact.get("stats") or {}).get("boundingBox"),"measurementCandidate":measurement,"texturedMeshOrDensePointCloud":artifact["artifactType"] in {"textured_mesh","dense_point_cloud"},"gaussianSplatPreviewOnly":preview,"modelFileExists":model_path.is_file()}


def import_artifact(project_id: str, source_path: Path, original_name: str, artifact_type: str, source_tool: str, notes: str, role: str | None) -> dict:
    job_progress_service.start(project_id, JOB_KEY, "upload_received", "Artifact upload received", progress_percent=5)
    if artifact_type not in ARTIFACT_TYPES or source_tool not in SOURCE_TOOLS or (role and role not in ROLES):
        job_progress_service.fail(project_id, JOB_KEY, "Unsupported artifact type, source tool, or role")
        raise ModelArtifactError("Unsupported artifact type, source tool, or role")
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        job_progress_service.fail(project_id, JOB_KEY, "Only .ply, .obj, and textured .zip model artifacts are supported")
        raise ModelArtifactError("Only .ply, .obj, and textured .zip model artifacts are supported")
    if not source_path.is_file():
        job_progress_service.fail(project_id, JOB_KEY, "Artifact file was not found")
        raise ModelArtifactError("Artifact file was not found")
    if suffix == ".zip":
        return _import_obj_bundle(project_id, source_path, original_name, artifact_type, source_tool, notes, role)
    target_dir = PROCESSED_DIR / project_id / "model_artifacts"
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(original_name).name
    target = target_dir / f"{uuid4()}_{safe_name}"
    job_progress_service.update(project_id, JOB_KEY, stage="storing_artifact_file", label="Storing artifact file", progress_percent=35)
    shutil.copyfile(source_path, target)
    job_progress_service.update(project_id, JOB_KEY, stage="parsing_model_metadata", label="Parsing model metadata", progress_percent=75)
    artifact = model_artifact_repository.add_artifact(project_id, artifact_type, source_tool, safe_name, target.stat().st_size,
        str(target), str(target.relative_to(PROCESSED_DIR)), notes, role, parse_stats(target))
    job_progress_service.complete(project_id, JOB_KEY, "Model artifact import complete")
    return artifact


def summary(project_id: str) -> dict:
    artifacts = model_artifact_repository.list_artifacts(project_id)
    for artifact in artifacts:
        if _is_gaussian_splat(artifact) and artifact["artifactType"] != "gaussian_splat":
            artifact["importWarning"] = "Gaussian Splat header detected. Preview-only. Not measurement-grade; do not use as finished/current progress comparison input."
    measurement_artifacts = [item for item in artifacts if item["artifactType"] in {"dense_point_cloud", "mesh", "textured_mesh"} and not _is_gaussian_splat(item)]
    latest = lambda collection, predicate: next((item for item in collection if predicate(item)), None)
    ready_artifacts = [item for item in measurement_artifacts if item.get("status") == "ready"]
    realityscan_artifacts = [item for item in ready_artifacts if item.get("source_type") == "realityscan"]
    raw_realityscan_artifacts = [item for item in realityscan_artifacts if item.get("artifactRole") == "raw_realityscan"]
    renderable = lambda item: (item.get("format") or Path((item.get("bundle") or {}).get("mainObjPath") or item["storagePath"]).suffix.lstrip(".").lower()) in {"obj", "glb", "gltf"}
    preferred = next((item for item in ready_artifacts if _viewer_ready_for_browser(item)), None)
    preferred = preferred or next((item for item in ready_artifacts if item.get("artifactRole") == "cleaned_mesh" and renderable(item)), None)
    preferred = preferred or next((item for item in raw_realityscan_artifacts if renderable(item)), None)
    reference = latest(measurement_artifacts, lambda item: item["role"] == "finished_reference")
    current = latest(measurement_artifacts, lambda item: item["role"] == "current_state")
    comparisons = model_artifact_repository.list_comparisons(project_id)
    measurement_ids = {item["artifactId"] for item in measurement_artifacts}
    measurement_comparisons = [item for item in comparisons if item["referenceArtifactId"] in measurement_ids and item["currentArtifactId"] in measurement_ids and item["referenceArtifactId"] != item["currentArtifactId"]]
    comparison_ready = bool(reference and current and reference["artifactId"] != current["artifactId"])
    if current and not reference:
        message = "Current-state model imported. Finished reference model is still needed."
    elif reference and not current:
        message = "Finished reference imported. Current-state model is still needed."
    elif comparison_ready and not measurement_comparisons:
        message = "Reference and current-state models are available. Create a comparison record from Model Artifacts."
    elif measurement_comparisons:
        message = "Comparison foundation ready. External alignment/distance analysis required."
    else:
        message = "Progress comparison requires two distinct artifacts: a finished reference and a current-state model."
    return {"artifacts": artifacts, "measurementArtifactCount": len(measurement_artifacts),
            "comparisonCandidates": [comparison_candidate(item) for item in artifacts],
            "latestDensePointCloud": latest(measurement_artifacts, lambda item: item["artifactType"] == "dense_point_cloud"),
            "latestMesh": latest(realityscan_artifacts, lambda item: item["artifactType"] == "textured_mesh") or latest(measurement_artifacts, lambda item: item["artifactType"] in {"mesh", "textured_mesh"}), "latestReferenceModel": reference,
            "latestCurrentStateModel": current, "comparisonReady": comparison_ready, "comparisonCount": len(measurement_comparisons),
            "latestComparison": measurement_comparisons[0] if measurement_comparisons else None, "preferredModelArtifact": preferred, "message": message}


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
