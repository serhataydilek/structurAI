from datetime import datetime, timezone
from pathlib import Path
import math
import shutil
import subprocess
from typing import Any

from app.database import PROCESSED_DIR
from app.repositories import capture_repository, reconstruction_repository, project_repository
from app.services import processing_service

SPARSE_NEXT_STEP = "Dense reconstruction / point cloud visualization"
POINT_CLOUD_MAX_POINTS = 50000
DENSE_POINT_CLOUD_MAX_POINTS = 100000
LIKELY_FAILURE_CAUSES = [
    "too few frames",
    "blurry capture",
    "low overlap",
    "plain walls / low texture",
    "mirrors or glass",
    "poor lighting",
    "COLMAP missing from PATH",
]
RECOMMENDED_FIXES = [
    "capture more frames",
    "move slower",
    "use better lighting",
    "avoid blank walls",
    "avoid mirrors/glass",
    "add textured objects",
    "try Detailed 3 FPS extraction",
    "try Video Sequential matching",
]
DENSE_FAILURE_CAUSES = [
    "sparse reconstruction too weak",
    "too few overlapping frames",
    "low texture",
    "blurry frames",
    "insufficient camera coverage",
    "COLMAP dense step failed",
    "CPU-only COLMAP may take a long time",
]
LOW_REGISTRATION_RECOMMENDATIONS = [
    "Move slower",
    "Keep the same objects visible across frames",
    "Capture in a loop",
    "Add textured objects, posters, or books to plain rooms",
    "Avoid blank walls, mirrors, glass, and shiny surfaces",
    "Try Detailed 3 FPS",
    "Try Video Sequential matching",
    "Use better lighting",
]
CUDA_DENSE_FAILURE_MESSAGE = (
    "Dense stereo reconstruction likely requires a CUDA-enabled COLMAP build. "
    "Your current COLMAP installation appears to be without CUDA support. "
    "Sparse reconstruction can still work, but dense reconstruction may not run with this build."
)
COLMAP_WITHOUT_CUDA_HINT = "COLMAP appears to be installed without CUDA support. Dense stereo may fail."
MATCHING_MODES = {"Auto", "Video Sequential", "Photo Exhaustive"}
SPARSE_MODEL_FILES = (("cameras.bin", "images.bin", "points3D.bin"), ("cameras.txt", "images.txt", "points3D.txt"))


class ReconstructionError(Exception):
    pass


def _colmap_path() -> str | None:
    path_colmap = shutil.which("colmap") or shutil.which("COLMAP.bat")
    if path_colmap:
        return path_colmap

    local_windows_install = Path("C:/Tools/COLMAP/COLMAP.bat")
    if local_windows_install.exists():
        return str(local_windows_install)

    return None


def _run_version(colmap: str) -> str | None:
    for args in ([colmap, "-h"], [colmap, "--help"]):
        try:
            result = _run_command(args, timeout_seconds=15)
        except (OSError, subprocess.TimeoutExpired):
            continue
        output = f"{result.stdout or ''}\n{result.stderr or ''}".strip().splitlines()
        if output:
            useful = [line.strip() for line in output if line.strip()][:12]
            return "\n".join(useful)[:900]
    return None


def _colmap_cuda_status(version_output: str | None) -> tuple[str | None, bool | str]:
    if not version_output:
        return None, "unknown"
    lowered = version_output.lower()
    if "without cuda" in lowered or "cuda: no" in lowered or "cuda support: no" in lowered:
        return COLMAP_WITHOUT_CUDA_HINT, False
    if "with cuda" in lowered or "cuda: yes" in lowered or "cuda support: yes" in lowered:
        return "COLMAP appears to include CUDA support.", True
    return "COLMAP was detected, but CUDA dense-stereo support could not be confirmed.", "unknown"


def diagnostics() -> dict[str, Any]:
    colmap = _colmap_path()
    version = _run_version(colmap) if colmap else None
    cuda_hint, dense_likely_available = _colmap_cuda_status(version)
    return {
        "colmapAvailable": bool(colmap),
        "colmapPath": colmap,
        "colmapVersion": version,
        "colmapCudaHint": cuda_hint,
        "denseReconstructionLikelyAvailable": dense_likely_available,
    }


def _workspace(project_id: str) -> dict[str, Path]:
    root = PROCESSED_DIR / project_id / "reconstruction" / "colmap"
    paths = {
        "root": root,
        "database": root / "database.db",
        "sparse": root / "sparse",
        "dense": root / "dense",
        "dense_workspace": root / "dense" / "workspace",
        "dense_logs": root / "dense" / "logs",
        "exports": root / "exports",
        "logs": root / "logs",
    }
    for key, path in paths.items():
        if key != "database":
            path.mkdir(parents=True, exist_ok=True)
    return paths


def _frames_dir(project_id: str) -> Path:
    return PROCESSED_DIR / project_id / "frames"


def _frames(project_id: str) -> list[Path]:
    frames_dir = _frames_dir(project_id)
    if not frames_dir.exists():
        return []
    return sorted(frames_dir.glob("frame_*.jpg"))


def _safe_log_preview(path: Path, max_chars: int = 1600) -> str:
    if not path.exists():
        return ""
    lines = [line.rstrip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    useful = lines[-24:]
    return "\n".join(useful)[-max_chars:]


def _log_files(paths: dict[str, Path]) -> list[str]:
    return [str(path) for path in sorted(paths["logs"].glob("*.log"))]


def _dense_log_files(paths: dict[str, Path]) -> list[str]:
    return [str(path) for path in sorted(paths["dense_logs"].glob("*.log"))]


def _log_preview_summary(log_files: list[str]) -> dict[str, str]:
    previews: dict[str, str] = {}
    for log_file in log_files:
        path = Path(log_file)
        name = path.name
        if name == "feature_extractor.log":
            previews["featureExtraction"] = _safe_log_preview(path)
        elif name in {"sequential_matcher.log", "exhaustive_matcher.log"}:
            previews["matcher"] = _safe_log_preview(path)
        elif name == "mapper.log":
            previews["mapper"] = _safe_log_preview(path)
    return previews


def _dense_log_preview_summary(log_files: list[str]) -> dict[str, str]:
    previews: dict[str, str] = {}
    for log_file in log_files:
        path = Path(log_file)
        name = path.name
        if name == "image_undistorter.log":
            previews["imageUndistorter"] = _safe_log_preview(path)
        elif name == "patch_match_stereo.log":
            previews["patchMatchStereo"] = _safe_log_preview(path)
        elif name == "stereo_fusion.log":
            previews["stereoFusion"] = _safe_log_preview(path)
    return previews


def _logs_contain_cuda_failure(previews: dict[str, str]) -> bool:
    text = "\n".join(previews.values()).lower()
    if not text:
        return False
    cuda_markers = ("cuda", "gpu", "no device", "device not found", "not compiled with cuda", "without cuda")
    return any(marker in text for marker in cuda_markers)


def _dense_support_likely_missing(diag: dict[str, Any], dense_previews: dict[str, str] | None = None) -> bool:
    if diag.get("denseReconstructionLikelyAvailable") is False:
        return True
    return _logs_contain_cuda_failure(dense_previews or {})


def _dense_likely_causes(diag: dict[str, Any], dense_previews: dict[str, str] | None = None) -> list[str]:
    causes = list(DENSE_FAILURE_CAUSES)
    if _dense_support_likely_missing(diag, dense_previews):
        return ["COLMAP build appears to be without CUDA/dense stereo support", *causes]
    return causes


def _export_dir(paths: dict[str, Path]) -> Path:
    return paths["exports"] / "txt"


def _sparse_model_folders(paths: dict[str, Path]) -> list[str]:
    if not paths["sparse"].exists():
        return []
    return [path.name for path in sorted(paths["sparse"].iterdir()) if path.is_dir()]


def _is_valid_sparse_model_folder(path: Path) -> bool:
    return path.is_dir() and any(all((path / filename).exists() for filename in filenames) for filenames in SPARSE_MODEL_FILES)


def _detected_sparse_model_path(paths: dict[str, Path]) -> Path | None:
    if not paths["sparse"].exists():
        return None
    candidates = [path for path in sorted(paths["sparse"].iterdir()) if _is_valid_sparse_model_folder(path)]
    if candidates:
        return candidates[0]
    return None


def _colmap_folder_listing(paths: dict[str, Path]) -> dict[str, list[str]]:
    root = paths["root"]
    listing: dict[str, list[str]] = {}
    if not root.exists():
        return listing
    for path in [root, paths["sparse"], paths["exports"], paths["dense"], paths["dense_workspace"], paths["dense_logs"]]:
        if path.exists() and path.is_dir():
            try:
                listing[str(path)] = sorted(item.name for item in path.iterdir())
            except OSError:
                listing[str(path)] = ["<unable to list>"]
        else:
            listing[str(path)] = []
    return listing


def _sparse_model_missing_message(paths: dict[str, Path]) -> str:
    expected_path = paths["sparse"]
    return (
        "Sparse model files were not found at expected COLMAP output path. "
        f"Expected sparse path: {expected_path}. "
        f"Path exists: {expected_path.exists()}. "
        f"Found under reconstruction/colmap: {_colmap_folder_listing(paths)}. "
        "Recommended fix: rerun sparse reconstruction and confirm COLMAP mapper generated cameras/images/points3D files before running dense reconstruction."
    )


def _sparse_output_exists(paths: dict[str, Path]) -> bool:
    return _detected_sparse_model_path(paths) is not None


def _point_file(paths: dict[str, Path]) -> Path:
    return _export_dir(paths) / "points3D.txt"


def _dense_point_file(paths: dict[str, Path]) -> Path:
    return paths["dense_workspace"] / "fused.ply"


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * max(0.0, min(100.0, percentile)) / 100.0
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _parse_sparse_points(path: Path) -> list[dict[str, float | int]]:
    if not path.exists():
        return []

    points: list[dict[str, float | int]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 8:
                continue
            try:
                points.append(
                    {
                        "id": int(parts[0]),
                        "x": float(parts[1]),
                        "y": float(parts[2]),
                        "z": float(parts[3]),
                        "r": int(parts[4]),
                        "g": int(parts[5]),
                        "b": int(parts[6]),
                        "error": float(parts[7]),
                    }
                )
            except ValueError:
                continue
    return points


def _parse_points3d(path: Path, max_points: int = POINT_CLOUD_MAX_POINTS) -> dict[str, Any]:
    if not path.exists():
        return {
            "available": False,
            "source": "colmap_sparse",
            "pointCount": 0,
            "originalPointCount": 0,
            "returnedPointCount": 0,
            "points": [],
            "message": "Sparse point cloud export is not available.",
        }

    parsed = _parse_sparse_points(path)
    original_count = len(parsed)
    if original_count > max_points:
        step = max(1, original_count // max_points)
        parsed = parsed[::step][:max_points]

    return {
        "available": original_count > 0,
        "source": "colmap_sparse",
        "pointCount": original_count,
        "originalPointCount": original_count,
        "returnedPointCount": len(parsed),
        "points": parsed,
        "message": "Sparse COLMAP point cloud loaded." if original_count else "No sparse points were found in the COLMAP export.",
    }


def _parse_ply_points(path: Path, max_points: int = DENSE_POINT_CLOUD_MAX_POINTS) -> dict[str, Any]:
    if not path.exists():
        return {
            "available": False,
            "source": "colmap_dense",
            "pointCount": 0,
            "originalPointCount": 0,
            "returnedPointCount": 0,
            "points": [],
            "message": "Dense point cloud output is not available.",
        }

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        header: list[str] = []
        for line in handle:
            header.append(line.strip())
            if line.strip() == "end_header":
                break

        if not header or header[0] != "ply" or "format ascii" not in "\n".join(header[:4]):
            return {
                "available": False,
                "source": "colmap_dense",
                "pointCount": 0,
                "originalPointCount": 0,
                "returnedPointCount": 0,
                "points": [],
                "message": "Dense PLY exists but is not an ASCII PLY file that this preview can parse.",
            }

        vertex_count = 0
        properties: list[str] = []
        in_vertex = False
        for line in header:
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "element":
                in_vertex = parts[1] == "vertex"
                if in_vertex:
                    vertex_count = int(parts[2])
                continue
            if in_vertex and len(parts) >= 3 and parts[0] == "property":
                properties.append(parts[-1])

        prop_index = {name: index for index, name in enumerate(properties)}
        required = {"x", "y", "z"}
        if not required.issubset(prop_index):
            return {
                "available": False,
                "source": "colmap_dense",
                "pointCount": vertex_count,
                "originalPointCount": vertex_count,
                "returnedPointCount": 0,
                "points": [],
                "message": "Dense PLY is missing x/y/z vertex properties.",
            }

        step = max(1, vertex_count // max_points) if vertex_count > max_points else 1
        parsed: list[dict[str, float | int]] = []
        for index in range(vertex_count):
            line = handle.readline()
            if not line:
                break
            if index % step != 0 or len(parsed) >= max_points:
                continue
            parts = line.split()
            try:
                r_index = prop_index.get("red")
                g_index = prop_index.get("green")
                b_index = prop_index.get("blue")
                parsed.append(
                    {
                        "x": float(parts[prop_index["x"]]),
                        "y": float(parts[prop_index["y"]]),
                        "z": float(parts[prop_index["z"]]),
                        "r": int(float(parts[r_index])) if r_index is not None and r_index < len(parts) else 210,
                        "g": int(float(parts[g_index])) if g_index is not None and g_index < len(parts) else 220,
                        "b": int(float(parts[b_index])) if b_index is not None and b_index < len(parts) else 230,
                    }
                )
            except (ValueError, IndexError):
                continue

    return {
        "available": vertex_count > 0 and len(parsed) > 0,
        "source": "colmap_dense",
        "pointCount": vertex_count,
        "originalPointCount": vertex_count,
        "returnedPointCount": len(parsed),
        "points": parsed,
        "message": "Dense COLMAP point cloud loaded." if parsed else "No dense points could be parsed from the COLMAP PLY.",
    }


def _point_cloud_available(paths: dict[str, Path]) -> bool:
    return _parse_points3d(_point_file(paths), max_points=1)["available"]


def _point_count(paths: dict[str, Path]) -> int:
    return int(_parse_points3d(_point_file(paths), max_points=1)["originalPointCount"])


def _dense_point_cloud_available(paths: dict[str, Path]) -> bool:
    return _parse_ply_points(_dense_point_file(paths), max_points=1)["available"]


def _dense_point_count(paths: dict[str, Path]) -> int:
    return int(_parse_ply_points(_dense_point_file(paths), max_points=1)["originalPointCount"])


def _images_txt_path(paths: dict[str, Path]) -> Path | None:
    exported = _export_dir(paths) / "images.txt"
    if exported.exists():
        return exported
    sparse_model_path = _detected_sparse_model_path(paths)
    if sparse_model_path and (sparse_model_path / "images.txt").exists():
        return sparse_model_path / "images.txt"
    return None


def _rotation_matrix_from_qvec(qvec: list[float]) -> list[list[float]]:
    qw, qx, qy, qz = qvec
    return [
        [1 - 2 * qy * qy - 2 * qz * qz, 2 * qx * qy - 2 * qz * qw, 2 * qx * qz + 2 * qy * qw],
        [2 * qx * qy + 2 * qz * qw, 1 - 2 * qx * qx - 2 * qz * qz, 2 * qy * qz - 2 * qx * qw],
        [2 * qx * qz - 2 * qy * qw, 2 * qy * qz + 2 * qx * qw, 1 - 2 * qx * qx - 2 * qy * qy],
    ]


def _camera_center_from_pose(qvec: list[float], tvec: list[float]) -> dict[str, float]:
    rotation = _rotation_matrix_from_qvec(qvec)
    return {
        "x": -(rotation[0][0] * tvec[0] + rotation[1][0] * tvec[1] + rotation[2][0] * tvec[2]),
        "y": -(rotation[0][1] * tvec[0] + rotation[1][1] * tvec[1] + rotation[2][1] * tvec[2]),
        "z": -(rotation[0][2] * tvec[0] + rotation[1][2] * tvec[1] + rotation[2][2] * tvec[2]),
    }


def _camera_path(paths: dict[str, Path]) -> dict[str, Any]:
    images_txt = _images_txt_path(paths)
    if not images_txt:
        return {
            "available": False,
            "positions": [],
            "message": "COLMAP images.txt is not available; camera path cannot be estimated.",
        }

    positions: list[dict[str, Any]] = []
    try:
        lines = images_txt.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) < 10:
                continue
            try:
                image_id = int(parts[0])
                qvec = [float(parts[index]) for index in range(1, 5)]
                tvec = [float(parts[index]) for index in range(5, 8)]
                image_name = parts[9]
            except ValueError:
                continue
            center = _camera_center_from_pose(qvec, tvec)
            positions.append({"imageId": image_id, "imageName": image_name, **center})
    except OSError as exc:
        return {"available": False, "positions": [], "message": f"Unable to parse camera path: {exc}"}

    positions.sort(key=lambda item: item["imageId"])
    return {
        "available": len(positions) > 0,
        "positions": positions[:500],
        "message": "Camera path estimated from COLMAP registered image poses." if positions else "No registered image poses were found in images.txt.",
    }


def _registered_image_count(paths: dict[str, Path]) -> int:
    return len(_camera_path(paths)["positions"])


def _registration_ratio(registered_image_count: int, extracted_frame_count: int) -> float:
    if extracted_frame_count <= 0:
        return 0.0
    return round(registered_image_count / extracted_frame_count, 3)


def _sparse_quality_label(registered_image_count: int, registration_ratio: float, sparse_point_count: int) -> str:
    if registered_image_count >= 30 and registration_ratio >= 0.30 and sparse_point_count >= 10000:
        return "Strong Sparse Reconstruction"
    if registered_image_count >= 10 and registration_ratio >= 0.15 and sparse_point_count >= 3000:
        return "Usable Sparse Reconstruction"
    return "Poor Sparse Reconstruction"


def _dense_readiness(
    sparse_status: str,
    dense_likely_available: bool | str,
    registered_image_count: int,
    extracted_frame_count: int,
    sparse_point_count: int,
    sparse_quality_label: str,
) -> dict[str, Any]:
    reasons: list[str] = []
    if sparse_status != "Sparse Reconstruction Complete":
        reasons.append("sparse reconstruction is not complete")
    if dense_likely_available is False:
        reasons.append("current COLMAP build lacks CUDA")
    if registered_image_count < 10:
        reasons.append(f"only {registered_image_count}/{extracted_frame_count} frames were registered")
    if sparse_quality_label == "Poor Sparse Reconstruction":
        reasons.append("sparse point cloud is too weak")
    if sparse_point_count < 3000:
        reasons.append("capture needs more overlap / texture")
    return {
        "ready": len(reasons) == 0,
        "recommended": len(reasons) == 0,
        "reasons": reasons,
    }


def _scene_confidence(point_count: int, width: float, depth: float, height: float, camera_count: int) -> str:
    meaningful_dimensions = sum(1 for value in (width, depth, height) if value > 0.25)
    if point_count >= 4000 and meaningful_dimensions >= 3 and camera_count >= 10:
        return "High"
    if point_count >= 700 and meaningful_dimensions >= 2:
        return "Medium"
    return "Low"


def scene_analysis(project_id: str) -> dict[str, Any] | None:
    if not project_repository.get_project(project_id):
        return None

    paths = _workspace(project_id)
    points = _parse_sparse_points(_point_file(paths))
    diag = diagnostics()
    dense_support_missing = diag["denseReconstructionLikelyAvailable"] is False
    if not points:
        return {
            "available": False,
            "pointCount": 0,
            "boundingBox": None,
            "center": None,
            "scale": 1,
            "floorEstimate": None,
            "roomScaffold": None,
            "cameraPath": _camera_path(paths),
            "confidence": "Low",
            "warnings": ["Sparse point cloud is not available; scene analysis cannot estimate room bounds."],
            "message": "Run sparse reconstruction before opening the sparse scene preview.",
        }

    xs = [float(point["x"]) for point in points]
    ys = [float(point["y"]) for point in points]
    zs = [float(point["z"]) for point in points]
    raw_min_x, raw_max_x = min(xs), max(xs)
    raw_min_y, raw_max_y = min(ys), max(ys)
    raw_min_z, raw_max_z = min(zs), max(zs)
    robust_min_x, robust_max_x = _percentile(xs, 2), _percentile(xs, 98)
    robust_min_y, robust_max_y = _percentile(ys, 2), _percentile(ys, 98)
    robust_min_z, robust_max_z = _percentile(zs, 2), _percentile(zs, 98)

    center = {
        "x": (robust_min_x + robust_max_x) / 2,
        "y": (robust_min_y + robust_max_y) / 2,
        "z": (robust_min_z + robust_max_z) / 2,
    }
    width = max(0.0, robust_max_x - robust_min_x)
    height = max(0.0, robust_max_y - robust_min_y)
    depth = max(0.0, robust_max_z - robust_min_z)
    max_dimension = max(width, height, depth, 0.001)
    scale = 4 / max_dimension
    floor_level = _percentile(ys, 5)
    camera_path = _camera_path(paths)
    confidence = _scene_confidence(len(points), width, depth, height, len(camera_path["positions"]))

    warnings = [
        "Room scaffold is estimated from sparse feature points, not measured geometry.",
        "Sparse bounding boxes may include outliers from reflective, repeated, or distant features.",
    ]
    if len(points) < 1000:
        warnings.insert(0, "Sparse point count is low; scene bounds may be unstable.")
    if dense_support_missing:
        warnings.append("Dense reconstruction requires a CUDA-enabled COLMAP build on this machine.")

    return {
        "available": True,
        "pointCount": len(points),
        "boundingBox": {
            "minX": raw_min_x,
            "maxX": raw_max_x,
            "minY": raw_min_y,
            "maxY": raw_max_y,
            "minZ": raw_min_z,
            "maxZ": raw_max_z,
            "robustMinX": robust_min_x,
            "robustMaxX": robust_max_x,
            "robustMinY": robust_min_y,
            "robustMaxY": robust_max_y,
            "robustMinZ": robust_min_z,
            "robustMaxZ": robust_max_z,
        },
        "center": center,
        "scale": scale,
        "suggestedCameraTarget": center,
        "suggestedCameraDistance": max_dimension * 1.45,
        "floorEstimate": {
            "axis": "y",
            "level": floor_level,
            "method": "5th percentile of sparse point Y coordinates",
        },
        "roomScaffold": {
            "width": width,
            "depth": depth,
            "height": height,
            "minX": robust_min_x,
            "maxX": robust_max_x,
            "minY": floor_level,
            "maxY": robust_max_y,
            "minZ": robust_min_z,
            "maxZ": robust_max_z,
        },
        "cameraPath": camera_path,
        "confidence": confidence,
        "warnings": warnings,
        "message": "Sparse scene preview combines real COLMAP sparse points with estimated room bounds for readability.",
    }


def normalize_matching_mode(mode: str | None) -> str:
    if not mode:
        return "Auto"
    normalized = mode.strip().lower()
    for label in MATCHING_MODES:
        if normalized == label.lower():
            return label
    raise ReconstructionError("Matching mode must be Auto, Video Sequential, or Photo Exhaustive.")


def _matching_mode_to_use(requested_mode: str, project_id: str) -> str:
    if requested_mode != "Auto":
        return requested_mode
    capture = capture_repository.get_capture_metadata(project_id)
    return "Video Sequential" if capture and capture["video_count"] > 0 else "Photo Exhaustive"


def _capture_fps_metadata(project_id: str) -> tuple[str, int]:
    capture = capture_repository.get_capture_metadata(project_id)
    if not capture:
        return "Balanced", 2
    return capture["selected_fps_mode"], int(capture["extraction_fps"])


def _next_action(sparse_status: str, dense_status: str, dense_support_missing: bool = False, sparse_quality_label: str = "Poor Sparse Reconstruction") -> str:
    if dense_status == "Dense Reconstruction Complete":
        return "Generate mesh / GLB export"
    if dense_status == "Dense Reconstruction Failed":
        if dense_support_missing:
            return "Continue with sparse scene preview or install a CUDA-enabled COLMAP build"
        return "Review dense logs and retry dense reconstruction"
    if sparse_status in {"Not Started", "Reconstructing Sparse Model"}:
        return "Run sparse reconstruction"
    if sparse_status == "Sparse Reconstruction Failed":
        return "Improve capture quality and rerun sparse reconstruction"
    if sparse_status == "Sparse Reconstruction Complete" and sparse_quality_label == "Poor Sparse Reconstruction":
        return "Improve capture and rerun sparse reconstruction"
    if sparse_status == "Sparse Reconstruction Complete" and dense_support_missing:
        return "Continue with sparse scene preview or install a CUDA-enabled COLMAP build"
    if sparse_status == "Sparse Reconstruction Complete" and dense_status in {"Dense Reconstruction Not Started", "Dense Reconstruction Running"}:
        return "Run dense reconstruction"
    return "Run sparse reconstruction"


def _matching_mode_display(metadata: dict[str, Any] | None, sparse_status: str) -> str:
    if not metadata:
        return "Not Started"
    matching_mode = metadata.get("matching_mode") or ""
    if sparse_status == "Sparse Reconstruction Complete" and matching_mode in {"", "Auto", "Not Started"}:
        return "Unknown / legacy sparse run"
    return matching_mode or "Not Started"


def _viewer_mode(paths: dict[str, Path]) -> str:
    if _dense_point_cloud_available(paths):
        return "dense_point_cloud"
    if _point_cloud_available(paths):
        return "sparse_point_cloud"
    return "prototype_preview"


def _run_command(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    use_shell = command[0].lower().endswith((".bat", ".cmd"))
    if use_shell:
        return subprocess.run(subprocess.list2cmdline(command), capture_output=True, text=True, timeout=timeout_seconds, shell=True)
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds)


def _run_colmap_step(name: str, command: list[str], log_path: Path, timeout_seconds: int = 900) -> None:
    result = _run_command(command, timeout_seconds)
    log_path.write_text(
        "\n".join(
            [
                f"$ {' '.join(command)}",
                "",
                "[stdout]",
                result.stdout or "",
                "",
                "[stderr]",
                result.stderr or "",
            ]
        ),
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise ReconstructionError(f"COLMAP {name} failed. See {log_path.name} for details.")


def _convert_sparse_model(colmap: str, paths: dict[str, Path]) -> tuple[bool, str | None]:
    sparse_model_path = _detected_sparse_model_path(paths)
    if not sparse_model_path:
        return False, _sparse_model_missing_message(paths)

    export_dir = _export_dir(paths)
    if export_dir.exists():
        shutil.rmtree(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    try:
        _run_colmap_step(
            "model_converter",
            [
                colmap,
                "model_converter",
                "--input_path",
                str(sparse_model_path),
                "--output_path",
                str(export_dir),
                "--output_type",
                "TXT",
            ],
            paths["logs"] / "model_converter.log",
        )
    except (ReconstructionError, subprocess.TimeoutExpired, OSError) as exc:
        return False, f"Sparse model conversion failed: {exc}"

    if not _point_file(paths).exists():
        return False, "COLMAP model conversion completed but points3D.txt was not generated."
    return True, None


def _base_summary(project_id: str) -> dict[str, Any] | None:
    if not project_repository.get_project(project_id):
        return None

    paths = _workspace(project_id)
    metadata = reconstruction_repository.get_reconstruction_metadata(project_id)
    frame_count = len(_frames(project_id))
    diag = diagnostics()

    capture_fps_mode, extraction_fps = _capture_fps_metadata(project_id)

    if not metadata:
        dense_status = "Dense Reconstruction Not Started"
        sparse_status = "Not Started"
        viewer_mode = _viewer_mode(paths)
        sparse_point_count = _point_count(paths)
        registered_image_count = _registered_image_count(paths)
        registration_ratio = _registration_ratio(registered_image_count, frame_count)
        sparse_quality = _sparse_quality_label(registered_image_count, registration_ratio, sparse_point_count)
        dense_readiness = _dense_readiness(
            sparse_status,
            diag["denseReconstructionLikelyAvailable"],
            registered_image_count,
            frame_count,
            sparse_point_count,
            sparse_quality,
        )
        return {
            "projectId": project_id,
            "status": sparse_status,
            "sparseStatus": sparse_status,
            "denseStatus": dense_status,
            "colmapAvailable": diag["colmapAvailable"],
            "colmapPath": diag["colmapPath"],
            "colmapVersion": diag["colmapVersion"],
            "colmapCudaHint": diag["colmapCudaHint"],
            "denseReconstructionLikelyAvailable": diag["denseReconstructionLikelyAvailable"],
            "inputFrameCount": frame_count,
            "selectedFpsMode": capture_fps_mode,
            "extractionFps": extraction_fps,
            "matchingMode": "Auto",
            "matchingModeUsed": "Not Started",
            "sparseOutputExists": _sparse_output_exists(paths),
            "sparseModelFolders": _sparse_model_folders(paths),
            "sparsePointCloudAvailable": _point_cloud_available(paths),
            "pointCount": sparse_point_count,
            "sparsePointCount": sparse_point_count,
            "extractedFrameCount": frame_count,
            "registeredImageCount": registered_image_count,
            "registrationRatio": registration_ratio,
            "registrationRatioLabel": f"{registered_image_count}/{frame_count} frames registered" if frame_count else "No extracted frames",
            "sparseQualityLabel": sparse_quality,
            "sparseReconstructionQuality": sparse_quality,
            "denseReadiness": dense_readiness,
            "denseRecommended": dense_readiness["recommended"],
            "densePointCloudAvailable": _dense_point_cloud_available(paths),
            "densePointCount": _dense_point_count(paths),
            "exportPathStatus": "available" if _point_file(paths).exists() else "missing",
            "viewerModeRecommendation": viewer_mode,
            "currentBestViewerMode": viewer_mode,
            "logFiles": _log_files(paths),
            "logPreviews": {},
            "logPreviewSummary": {},
            "denseLogFiles": _dense_log_files(paths),
            "denseLogPreviewSummary": _dense_log_preview_summary(_dense_log_files(paths)),
            "denseEndpointAvailable": True,
            "detectedSparseModelPath": str(_detected_sparse_model_path(paths)) if _detected_sparse_model_path(paths) else None,
            "sparseModelPathExists": bool(_detected_sparse_model_path(paths)),
            "denseWorkspacePath": str(paths["dense_workspace"]),
            "denseLastError": None,
            "warnings": [],
            "errorMessage": None,
            "denseWarnings": [],
            "denseErrorMessage": None,
            "likelyCauses": [],
            "denseLikelyCauses": [],
            "lowRegistrationRecommendations": LOW_REGISTRATION_RECOMMENDATIONS if sparse_quality == "Poor Sparse Reconstruction" and registered_image_count > 0 else [],
            "recommendedFixes": [],
            "recommendedNextAction": _next_action(
                sparse_status,
                dense_status,
                _dense_support_likely_missing(diag, _dense_log_preview_summary(_dense_log_files(paths))),
                sparse_quality,
            ),
            "nextStep": SPARSE_NEXT_STEP,
        }

    previews = {
        Path(log_file).name: _safe_log_preview(Path(log_file))
        for log_file in metadata["log_files"]
    }
    sparse_status = metadata["status"]
    dense_status = metadata["dense_status"]
    viewer_mode = _viewer_mode(paths)
    dense_previews = _dense_log_preview_summary(metadata["dense_log_files"])
    dense_support_missing = _dense_support_likely_missing(diag, dense_previews)
    dense_error_message = (
        CUDA_DENSE_FAILURE_MESSAGE
        if dense_status == "Dense Reconstruction Failed" and dense_support_missing
        else metadata["dense_error_message"]
    )
    sparse_point_count = _point_count(paths)
    registered_image_count = _registered_image_count(paths)
    registration_ratio = _registration_ratio(registered_image_count, metadata["input_frame_count"])
    sparse_quality = _sparse_quality_label(registered_image_count, registration_ratio, sparse_point_count)
    dense_readiness = _dense_readiness(
        sparse_status,
        diag["denseReconstructionLikelyAvailable"],
        registered_image_count,
        metadata["input_frame_count"],
        sparse_point_count,
        sparse_quality,
    )
    return {
        "projectId": project_id,
        "status": sparse_status,
        "sparseStatus": sparse_status,
        "denseStatus": dense_status,
        "colmapAvailable": metadata["colmap_available"],
        "colmapPath": diag["colmapPath"],
        "colmapVersion": metadata["colmap_version"],
        "colmapCudaHint": diag["colmapCudaHint"],
        "denseReconstructionLikelyAvailable": diag["denseReconstructionLikelyAvailable"],
        "inputFrameCount": metadata["input_frame_count"],
        "selectedFpsMode": metadata["selected_fps_mode"],
        "extractionFps": metadata["extraction_fps"],
        "matchingMode": metadata["matching_mode"],
        "matchingModeUsed": _matching_mode_display(metadata, sparse_status),
        "sparseOutputExists": metadata["sparse_output_exists"],
        "sparseModelFolders": metadata["sparse_model_folders"],
        "sparsePointCloudAvailable": _point_cloud_available(paths),
        "pointCount": sparse_point_count,
        "sparsePointCount": sparse_point_count,
        "extractedFrameCount": metadata["input_frame_count"],
        "registeredImageCount": registered_image_count,
        "registrationRatio": registration_ratio,
        "registrationRatioLabel": f"{registered_image_count}/{metadata['input_frame_count']} frames registered" if metadata["input_frame_count"] else "No extracted frames",
        "sparseQualityLabel": sparse_quality,
        "sparseReconstructionQuality": sparse_quality,
        "denseReadiness": dense_readiness,
        "denseRecommended": dense_readiness["recommended"],
        "densePointCloudAvailable": _dense_point_cloud_available(paths),
        "densePointCount": _dense_point_count(paths),
        "exportPathStatus": "available" if _point_file(paths).exists() else "missing",
        "viewerModeRecommendation": viewer_mode,
        "currentBestViewerMode": viewer_mode,
        "logFiles": metadata["log_files"],
        "logPreviews": previews,
        "logPreviewSummary": _log_preview_summary(metadata["log_files"]),
        "denseLogFiles": metadata["dense_log_files"],
        "denseLogPreviewSummary": dense_previews,
        "denseEndpointAvailable": True,
        "detectedSparseModelPath": str(_detected_sparse_model_path(paths)) if _detected_sparse_model_path(paths) else None,
        "sparseModelPathExists": bool(_detected_sparse_model_path(paths)),
        "denseWorkspacePath": str(paths["dense_workspace"]),
        "denseLastError": dense_error_message,
        "warnings": metadata["warnings"],
        "errorMessage": metadata["error_message"],
        "denseWarnings": metadata["dense_warnings"],
        "denseErrorMessage": dense_error_message,
        "likelyCauses": LIKELY_FAILURE_CAUSES if sparse_status == "Sparse Reconstruction Failed" else [],
        "denseLikelyCauses": _dense_likely_causes(diag, dense_previews) if dense_status == "Dense Reconstruction Failed" else [],
        "lowRegistrationRecommendations": LOW_REGISTRATION_RECOMMENDATIONS if sparse_quality == "Poor Sparse Reconstruction" and registered_image_count > 0 else [],
        "recommendedFixes": RECOMMENDED_FIXES if sparse_status == "Sparse Reconstruction Failed" else [],
        "recommendedNextAction": _next_action(sparse_status, dense_status, dense_support_missing, sparse_quality),
        "nextStep": SPARSE_NEXT_STEP,
    }


def reconstruction_summary(project_id: str) -> dict[str, Any] | None:
    return _base_summary(project_id)


def run_sparse_reconstruction(project_id: str, matching_mode: str | None = None) -> dict[str, Any]:
    project = project_repository.get_project(project_id)
    if not project:
        raise ReconstructionError("Project not found")

    frames = _frames(project_id)
    if not frames:
        raise ReconstructionError("No extracted frames found. Process the capture before running sparse reconstruction.")

    requested_matching_mode = normalize_matching_mode(matching_mode)
    matching_mode_used = _matching_mode_to_use(requested_matching_mode, project_id)
    capture_fps_mode, extraction_fps = _capture_fps_metadata(project_id)

    diag = diagnostics()
    if not diag["colmapAvailable"] or not diag["colmapPath"]:
        warnings = ["COLMAP is not available on PATH. Install COLMAP and verify with colmap -h or COLMAP.bat -h."]
        reconstruction_repository.upsert_reconstruction_metadata(
            project_id=project_id,
            status="Sparse Reconstruction Failed",
            colmap_available=False,
            colmap_version=None,
            input_frame_count=len(frames),
            selected_fps_mode=capture_fps_mode,
            extraction_fps=extraction_fps,
            matching_mode=matching_mode_used,
            sparse_output_exists=False,
            sparse_model_folders=[],
            log_files=[],
            warnings=warnings,
            error_message="COLMAP is required for sparse reconstruction but was not detected on PATH.",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        project_repository.set_status(project_id, "Sparse Reconstruction Failed")
        raise ReconstructionError("COLMAP is required for sparse reconstruction but was not detected on PATH.")

    paths = _workspace(project_id)
    if paths["database"].exists():
        paths["database"].unlink()
    for item in paths["sparse"].iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        elif item.is_file():
            item.unlink()
    if paths["exports"].exists():
        shutil.rmtree(paths["exports"])
    paths["exports"].mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc).isoformat()
    project_repository.set_status(project_id, "Reconstructing Sparse Model")
    reconstruction_repository.upsert_reconstruction_metadata(
        project_id=project_id,
        status="Reconstructing Sparse Model",
        colmap_available=True,
        colmap_version=diag["colmapVersion"],
        input_frame_count=len(frames),
        selected_fps_mode=capture_fps_mode,
        extraction_fps=extraction_fps,
        matching_mode=matching_mode_used,
        sparse_output_exists=False,
        sparse_model_folders=[],
        log_files=[],
        warnings=[],
        error_message=None,
        started_at=started_at,
    )

    colmap = diag["colmapPath"]
    try:
        _run_colmap_step(
            "feature_extractor",
            [
                colmap,
                "feature_extractor",
                "--database_path",
                str(paths["database"]),
                "--image_path",
                str(_frames_dir(project_id)),
                "--ImageReader.single_camera",
                "1",
            ],
            paths["logs"] / "feature_extractor.log",
        )
        if matching_mode_used == "Video Sequential":
            _run_colmap_step(
                "sequential_matcher",
                [colmap, "sequential_matcher", "--database_path", str(paths["database"])],
                paths["logs"] / "sequential_matcher.log",
            )
        else:
            _run_colmap_step(
                "exhaustive_matcher",
                [colmap, "exhaustive_matcher", "--database_path", str(paths["database"])],
                paths["logs"] / "exhaustive_matcher.log",
            )
        _run_colmap_step(
            "mapper",
            [
                colmap,
                "mapper",
                "--database_path",
                str(paths["database"]),
                "--image_path",
                str(_frames_dir(project_id)),
                "--output_path",
                str(paths["sparse"]),
            ],
            paths["logs"] / "mapper.log",
        )
    except (ReconstructionError, subprocess.TimeoutExpired, OSError) as exc:
        message = str(exc)
        reconstruction_repository.upsert_reconstruction_metadata(
            project_id=project_id,
            status="Sparse Reconstruction Failed",
            colmap_available=True,
            colmap_version=diag["colmapVersion"],
            input_frame_count=len(frames),
            selected_fps_mode=capture_fps_mode,
            extraction_fps=extraction_fps,
            matching_mode=matching_mode_used,
            sparse_output_exists=_sparse_output_exists(paths),
            sparse_model_folders=_sparse_model_folders(paths),
            log_files=_log_files(paths),
            warnings=["Sparse reconstruction failed. Check capture quality and COLMAP logs."],
            error_message=message,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        project_repository.set_status(project_id, "Sparse Reconstruction Failed")
        raise ReconstructionError(message) from exc

    sparse_exists = _sparse_output_exists(paths)
    conversion_ok = False
    conversion_warning = None
    if sparse_exists:
        conversion_ok, conversion_warning = _convert_sparse_model(colmap, paths)
    status = "Sparse Reconstruction Complete" if sparse_exists else "Sparse Reconstruction Failed"
    warnings = [] if sparse_exists else ["COLMAP completed but no sparse model files were found."]
    if conversion_warning:
        warnings.append(conversion_warning)
    reconstruction_repository.upsert_reconstruction_metadata(
        project_id=project_id,
        status=status,
        colmap_available=True,
        colmap_version=diag["colmapVersion"],
        input_frame_count=len(frames),
        selected_fps_mode=capture_fps_mode,
        extraction_fps=extraction_fps,
        matching_mode=matching_mode_used,
        sparse_output_exists=sparse_exists,
        sparse_model_folders=_sparse_model_folders(paths),
        log_files=_log_files(paths),
        warnings=warnings,
        error_message=None if sparse_exists else "No sparse model files were generated.",
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    project_repository.set_status(project_id, status)
    return reconstruction_summary(project_id) or {}


def run_dense_reconstruction(project_id: str) -> dict[str, Any]:
    project = project_repository.get_project(project_id)
    if not project:
        raise ReconstructionError("Project not found")

    metadata = reconstruction_repository.get_reconstruction_metadata(project_id)
    if not metadata or metadata["status"] != "Sparse Reconstruction Complete":
        raise ReconstructionError("Run sparse reconstruction successfully before dense reconstruction.")

    paths = _workspace(project_id)
    sparse_model_path = _detected_sparse_model_path(paths)
    if not sparse_model_path:
        message = _sparse_model_missing_message(paths)
        reconstruction_repository.update_dense_metadata(
            project_id=project_id,
            dense_status="Dense Reconstruction Failed",
            dense_output_exists=False,
            dense_point_count=0,
            dense_output_path=None,
            dense_log_files=_dense_log_files(paths),
            dense_warnings=["Sparse model files were missing before dense reconstruction could start."],
            dense_error_message=message,
        )
        raise ReconstructionError(message)

    diag = diagnostics()
    if not diag["colmapAvailable"] or not diag["colmapPath"]:
        reconstruction_repository.update_dense_metadata(
            project_id=project_id,
            dense_status="Dense Reconstruction Failed",
            dense_output_exists=False,
            dense_point_count=0,
            dense_output_path=None,
            dense_log_files=_dense_log_files(paths),
            dense_warnings=["COLMAP is required for dense reconstruction but was not detected on PATH."],
            dense_error_message="COLMAP is required for dense reconstruction but was not detected on PATH.",
        )
        raise ReconstructionError("COLMAP is required for dense reconstruction but was not detected on PATH.")

    if paths["dense_workspace"].exists():
        shutil.rmtree(paths["dense_workspace"])
    paths["dense_workspace"].mkdir(parents=True, exist_ok=True)
    paths["dense_logs"].mkdir(parents=True, exist_ok=True)

    reconstruction_repository.update_dense_metadata(
        project_id=project_id,
        dense_status="Dense Reconstruction Running",
        dense_output_exists=False,
        dense_point_count=0,
        dense_output_path=None,
        dense_log_files=_dense_log_files(paths),
        dense_warnings=["Dense reconstruction can take much longer than sparse reconstruction, especially without CUDA."],
        dense_error_message=None,
    )
    project_repository.set_status(project_id, "Dense Reconstruction Running")

    colmap = diag["colmapPath"]
    dense_output = _dense_point_file(paths)
    try:
        _run_colmap_step(
            "image_undistorter",
            [
                colmap,
                "image_undistorter",
                "--image_path",
                str(_frames_dir(project_id)),
                "--input_path",
                str(sparse_model_path),
                "--output_path",
                str(paths["dense_workspace"]),
                "--output_type",
                "COLMAP",
            ],
            paths["dense_logs"] / "image_undistorter.log",
            timeout_seconds=1800,
        )
        _run_colmap_step(
            "patch_match_stereo",
            [
                colmap,
                "patch_match_stereo",
                "--workspace_path",
                str(paths["dense_workspace"]),
                "--workspace_format",
                "COLMAP",
            ],
            paths["dense_logs"] / "patch_match_stereo.log",
            timeout_seconds=7200,
        )
        _run_colmap_step(
            "stereo_fusion",
            [
                colmap,
                "stereo_fusion",
                "--workspace_path",
                str(paths["dense_workspace"]),
                "--workspace_format",
                "COLMAP",
                "--input_type",
                "geometric",
                "--output_path",
                str(dense_output),
            ],
            paths["dense_logs"] / "stereo_fusion.log",
            timeout_seconds=3600,
        )
    except (ReconstructionError, subprocess.TimeoutExpired, OSError) as exc:
        dense_previews = _dense_log_preview_summary(_dense_log_files(paths))
        message = CUDA_DENSE_FAILURE_MESSAGE if _dense_support_likely_missing(diag, dense_previews) else str(exc)
        warnings = [message] if message == CUDA_DENSE_FAILURE_MESSAGE else ["Dense reconstruction failed. Review dense logs and capture quality."]
        reconstruction_repository.update_dense_metadata(
            project_id=project_id,
            dense_status="Dense Reconstruction Failed",
            dense_output_exists=dense_output.exists(),
            dense_point_count=_dense_point_count(paths),
            dense_output_path=str(dense_output) if dense_output.exists() else None,
            dense_log_files=_dense_log_files(paths),
            dense_warnings=warnings,
            dense_error_message=message,
        )
        project_repository.set_status(project_id, "Dense Reconstruction Failed")
        raise ReconstructionError(message) from exc

    dense_available = _dense_point_cloud_available(paths)
    dense_count = _dense_point_count(paths)
    dense_status = "Dense Reconstruction Complete" if dense_available else "Dense Reconstruction Failed"
    warnings = [] if dense_available else ["COLMAP dense fusion completed but no parseable dense PLY points were found."]
    reconstruction_repository.update_dense_metadata(
        project_id=project_id,
        dense_status=dense_status,
        dense_output_exists=dense_available,
        dense_point_count=dense_count,
        dense_output_path=str(dense_output) if dense_output.exists() else None,
        dense_log_files=_dense_log_files(paths),
        dense_warnings=warnings,
        dense_error_message=None if dense_available else "No parseable dense point cloud was generated.",
    )
    project_repository.set_status(project_id, dense_status)
    return reconstruction_summary(project_id) or {}


def point_cloud(project_id: str, max_points: int = POINT_CLOUD_MAX_POINTS) -> dict[str, Any] | None:
    if not project_repository.get_project(project_id):
        return None
    paths = _workspace(project_id)
    max_points = max(1, min(max_points, POINT_CLOUD_MAX_POINTS))
    return _parse_points3d(_point_file(paths), max_points=max_points)


def dense_point_cloud(project_id: str, max_points: int = DENSE_POINT_CLOUD_MAX_POINTS) -> dict[str, Any] | None:
    if not project_repository.get_project(project_id):
        return None
    paths = _workspace(project_id)
    max_points = max(1, min(max_points, DENSE_POINT_CLOUD_MAX_POINTS))
    return _parse_ply_points(_dense_point_file(paths), max_points=max_points)
