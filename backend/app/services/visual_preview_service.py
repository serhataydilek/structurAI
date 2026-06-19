from pathlib import Path
import json
from datetime import datetime, timezone
import os
import shutil
import subprocess
import threading
from typing import Any
from uuid import uuid4

from app.database import PROCESSED_DIR
from app.repositories import project_repository, visual_preview_repository
from app.services import reconstruction_service

VISUAL_PREVIEW_TYPES = {
    "gaussian_splat_placeholder",
    "external_viewer",
    "future_visual_preview",
}
DEFAULT_PREVIEW_TYPE = "gaussian_splat_placeholder"
NEXT_STEP = "Train with Nerfstudio Splatfacto, then export Gaussian Splat assets."
TRAINING_PRESETS = {
    "smoke": 1,
    "quick": 1000,
    "demo": 7000,
    "quality": 30000,
}
DEFAULT_TRAINING_PRESET = "demo"
LOG_TAIL_LINES = 80
WINDOWS_CONDA_PATH_PARTS = (
    "bin",
    "",
    "Library\\mingw-w64\\bin",
    "Library\\usr\\bin",
    "Library\\bin",
    "Scripts",
)


class VisualPreviewError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _command_path(env_name: str, executable: str) -> str | None:
    configured = os.getenv(env_name)
    if configured:
        return configured if Path(configured).exists() or shutil.which(configured) else configured
    return shutil.which(executable)


def _conda_prefix_from_python(python_path: str | None) -> Path | None:
    if not python_path:
        return None
    path = Path(python_path)
    if path.name.lower() != "python.exe":
        return None
    return path.parent if path.exists() else None


def _nerfstudio_subprocess_env(python_path: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"
    env["NVCC_PREPEND_FLAGS"] = "-allow-unsupported-compiler"
    conda_prefix = _conda_prefix_from_python(python_path or os.getenv("NERFSTUDIO_PYTHON"))
    if os.name == "nt" and conda_prefix:
        env["CUDA_HOME"] = str(conda_prefix)
        env["CUDA_PATH"] = str(conda_prefix)
        env["CL"] = " ".join(
            [
                env.get("CL", ""),
                "/D_ALLOW_COMPILER_AND_STL_VERSION_MISMATCH",
                "/Usmall",
            ]
        ).strip()
        include_candidates = [
            conda_prefix / "include",
            conda_prefix / "Library" / "include" / "targets" / "x64" / "cccl",
        ]
        include_paths = [str(path) for path in include_candidates if path.exists()]
        if include_paths:
            env["INCLUDE"] = os.pathsep.join(include_paths + [env.get("INCLUDE", "")])
            env["CPLUS_INCLUDE_PATH"] = os.pathsep.join(include_paths + [env.get("CPLUS_INCLUDE_PATH", "")])
        certifi_bundle = conda_prefix / "Lib" / "site-packages" / "certifi" / "cacert.pem"
        if certifi_bundle.exists():
            env["SSL_CERT_FILE"] = str(certifi_bundle)
            env["REQUESTS_CA_BUNDLE"] = str(certifi_bundle)
        path_parts = [str(conda_prefix / part) if part else str(conda_prefix) for part in WINDOWS_CONDA_PATH_PARTS]
        env["PATH"] = os.pathsep.join(path_parts + [env.get("PATH", "")])
    return env


def _vcvars64_path() -> Path | None:
    candidates = [
        Path(r"C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"),
        Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"),
        Path(r"C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat"),
    ]
    return next((path for path in candidates if path.exists()), None)


def _windows_build_command(command: list[str]) -> tuple[list[str] | str, bool]:
    if os.name != "nt":
        return command, False
    vcvars = _vcvars64_path()
    if not vcvars:
        return command, False
    return f'call "{vcvars}" >nul && {subprocess.list2cmdline(command)}', True


def _run_nerfstudio_probe(command: list[str], python_path: str | None = None, timeout: int = 20) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_nerfstudio_subprocess_env(python_path),
        )
        return {
            "ok": result.returncode == 0,
            "returnCode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "returnCode": None, "stdout": "", "stderr": str(exc)}


def diagnostics() -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    nerfstudio_python = os.getenv("NERFSTUDIO_PYTHON") or shutil.which("python")
    ns_train = _command_path("NERFSTUDIO_NS_TRAIN", "ns-train")
    ns_export = _command_path("NERFSTUDIO_NS_EXPORT", "ns-export")
    cuda_likely: bool | str = "unknown"
    torch_cuda_version: str | None = None
    cuda_device_name: str | None = None
    if nerfstudio_python:
        probe = _run_nerfstudio_probe(
            [
                nerfstudio_python,
                "-c",
                "import json, torch; print(json.dumps({'cuda': torch.cuda.is_available(), 'torchCuda': torch.version.cuda, 'device': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}))",
            ],
            nerfstudio_python,
            timeout=20,
        )
        if probe["ok"]:
            try:
                torch_info = json.loads(probe["stdout"].splitlines()[-1])
                cuda_likely = bool(torch_info.get("cuda"))
                torch_cuda_version = torch_info.get("torchCuda")
                cuda_device_name = torch_info.get("device")
            except (json.JSONDecodeError, IndexError):
                errors.append("Torch CUDA probe returned unparseable output.")
        else:
            errors.append(f"Torch CUDA probe failed: {probe['stderr'] or probe['stdout']}")

    try:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        probe = PROCESSED_DIR / ".visual_preview_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        output_writable = True
    except OSError as exc:
        output_writable = False
        warnings.append(f"Processed output directory is not writable: {exc}")

    if not ns_train:
        warnings.append("ns-train was not found. Install Nerfstudio or set NERFSTUDIO_NS_TRAIN.")
    if not ns_export:
        warnings.append("ns-export was not found. Install Nerfstudio or set NERFSTUDIO_NS_EXPORT.")
    if ns_train:
        train_probe = _run_nerfstudio_probe([ns_train, "--help"], nerfstudio_python, timeout=60)
        if not (train_probe["ok"] or "Train a radiance field" in train_probe["stdout"]):
            errors.append(f"ns-train probe failed: {train_probe['stderr'] or train_probe['stdout']}")
    if ns_export:
        export_probe = _run_nerfstudio_probe([ns_export, "--help"], nerfstudio_python, timeout=60)
        if not (export_probe["ok"] or "gaussian-splat" in export_probe["stdout"]):
            errors.append(f"ns-export probe failed: {export_probe['stderr'] or export_probe['stdout']}")
    if cuda_likely is False:
        warnings.append("CUDA is not available to the configured Nerfstudio Python. Splatfacto training may be slow or fail.")

    nerfstudio_available = bool(ns_train and ns_export and output_writable and cuda_likely is True and not errors)
    setup = (
        "Nerfstudio is available for Visual Preview training."
        if nerfstudio_available
        else "Nerfstudio is not available on this machine. Install/configure Nerfstudio to train Gaussian Splat visual previews. Set NERFSTUDIO_PYTHON, NERFSTUDIO_NS_TRAIN, and NERFSTUDIO_NS_EXPORT if the commands are outside PATH."
    )
    return {
        "nerfstudioAvailable": nerfstudio_available,
        "nerfstudioPython": nerfstudio_python,
        "nsTrainPath": ns_train,
        "nsTrainFound": bool(ns_train),
        "nsExportPath": ns_export,
        "nsExportFound": bool(ns_export),
        "cudaLikelyAvailable": cuda_likely,
        "cudaAvailable": cuda_likely,
        "torchCudaVersion": torch_cuda_version,
        "cudaDeviceName": cuda_device_name,
        "outputDirectoryWritable": output_writable,
        "warnings": warnings,
        "errors": errors,
        "recommendedSetupMessage": setup,
    }


def _sparse_model_files(path: Path | None) -> dict[str, bool]:
    if not path:
        return {"cameras": False, "images": False, "points": False}
    return {
        "cameras": (path / "cameras.bin").exists() or (path / "cameras.txt").exists(),
        "images": (path / "images.bin").exists() or (path / "images.txt").exists(),
        "points": (path / "points3D.bin").exists() or (path / "points3D.txt").exists(),
    }


def _dataset_files(path: Path | None) -> dict[str, Any]:
    images_dir = path / "images" if path else None
    sparse_dir = path / "sparse" / "0" if path else None
    sparse_files = _sparse_model_files(sparse_dir)
    image_count = len([item for item in images_dir.iterdir() if item.is_file()]) if images_dir and images_dir.exists() else 0
    missing: list[str] = []
    if not images_dir or not images_dir.exists():
        missing.append("nerfstudio_dataset/images/")
    if not sparse_dir or not sparse_dir.exists():
        missing.append("nerfstudio_dataset/sparse/0/")
    for key, exists in sparse_files.items():
        if not exists:
            missing.append(f"nerfstudio_dataset/sparse/0/{key}")
    if image_count == 0:
        missing.append("registered source images")
    return {
        "ready": len(missing) == 0,
        "missing": missing,
        "imageCount": image_count,
        "imagesPath": str(images_dir) if images_dir else None,
        "sparsePath": str(sparse_dir) if sparse_dir else None,
        "sparseFiles": sparse_files,
    }


def _best_attempt(summary: dict[str, Any]) -> dict[str, Any] | None:
    return summary.get("bestAttempt") or summary.get("displayedAttempt") or summary.get("latestAttempt")


def _readiness(project_id: str, summary: dict[str, Any] | None) -> dict[str, Any]:
    reasons: list[str] = []
    checks: list[dict[str, Any]] = []
    attempt = _best_attempt(summary or {})
    quality = str((attempt or {}).get("sparseQualityLabel") or (summary or {}).get("sparseQualityLabel") or "Not evaluated")
    registered = int((attempt or {}).get("registeredImageCount") or (summary or {}).get("registeredImageCount") or 0)
    points = int((attempt or {}).get("sparsePointCount") or (summary or {}).get("sparsePointCount") or 0)
    sparse_status = str((attempt or {}).get("status") or (summary or {}).get("sparseStatus") or "Not Started")
    sparse_model_path = Path(summary["detectedSparseModelPath"]) if summary and summary.get("detectedSparseModelPath") else None
    model_files = _sparse_model_files(sparse_model_path)
    image_folder_value = (attempt or {}).get("selectedFrameFolder") or (summary or {}).get("selectedFrameFolder")
    image_folder = Path(image_folder_value) if image_folder_value else None
    image_folder_exists = bool(image_folder and image_folder.exists())

    def add_check(key: str, label: str, passed: bool, detail: str) -> None:
        checks.append({"key": key, "label": label, "passed": passed, "detail": detail})
        if not passed:
            reasons.append(detail)

    add_check(
        "sparse_attempt",
        "Sparse attempt exists",
        bool(attempt and sparse_status == "Sparse Reconstruction Complete"),
        "Run a successful sparse reconstruction first.",
    )
    add_check(
        "sparse_quality",
        "Sparse quality is usable or strong",
        quality in {"Usable Sparse Reconstruction", "Strong Sparse Reconstruction"},
        f"Sparse quality is {quality}; visual preview is not recommended for weak sparse reconstructions.",
    )
    add_check(
        "registered_images",
        "At least 20 registered images",
        registered >= 20,
        f"Only {registered} registered images were found; visual preview needs at least 20.",
    )
    add_check(
        "colmap_model",
        "COLMAP cameras, images, and points exist",
        all(model_files.values()),
        f"COLMAP sparse model files are incomplete at {sparse_model_path or 'unknown path'}.",
    )
    add_check(
        "image_folder",
        "Source image folder exists",
        image_folder_exists,
        f"Source image folder is missing: {image_folder or 'unknown path'}.",
    )

    ready = len(reasons) == 0
    return {
        "ready": ready,
        "recommended": ready,
        "label": "Good visual preview candidate" if ready else "Visual preview not recommended yet",
        "reasons": reasons,
        "checks": checks,
        "attempt": attempt,
        "registeredImageCount": registered,
        "sparsePointCount": points,
        "sparseQualityLabel": quality,
        "imageFolderPath": str(image_folder) if image_folder else None,
        "colmapModelPath": str(sparse_model_path) if sparse_model_path else None,
    }


def _registered_image_names(colmap_model_path: Path) -> list[str]:
    images_txt = colmap_model_path / "images.txt"
    if not images_txt.exists():
        return []
    names: list[str] = []
    for line in images_txt.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) >= 10:
            names.append(parts[9])
    return names


def _copy_tree_contents(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if item.is_dir():
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)


def _prepare_nerfstudio_dataset(preview: dict[str, Any]) -> Path:
    summary = preview.get("summaryJson") or {}
    output_path = Path(preview["outputPath"])
    dataset_dir = output_path / "nerfstudio_dataset"
    images_dir = dataset_dir / "images"
    sparse_dir = dataset_dir / "sparse" / "0"
    if dataset_dir.exists():
        shutil.rmtree(dataset_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
    sparse_dir.mkdir(parents=True, exist_ok=True)

    source_images = Path(str(summary.get("imageFolderPath") or ""))
    colmap_model = Path(str(summary.get("colmapModelPath") or ""))
    if not source_images.exists() or not colmap_model.exists():
        raise VisualPreviewError("Visual preview manifest is missing image or COLMAP model paths.")

    _copy_tree_contents(colmap_model, sparse_dir)
    registered_names = set(_registered_image_names(colmap_model))
    copied = 0
    for source in source_images.iterdir():
        if not source.is_file():
            continue
        if registered_names and source.name not in registered_names:
            continue
        shutil.copy2(source, images_dir / source.name)
        copied += 1
    if copied == 0:
        for source in source_images.iterdir():
            if source.is_file():
                shutil.copy2(source, images_dir / source.name)
                copied += 1

    # Adapter layout for Nerfstudio's COLMAP parser:
    # dataset/
    #   images/            registered images copied from the sparse attempt input folder
    #   sparse/0/          COLMAP cameras/images/points3D files
    # Nerfstudio can consume this with `ns-train splatfacto --data <dataset>`.
    adapter_metadata = {
        "layout": "nerfstudio_colmap_adapter",
        "imageCount": copied,
        "registeredImageFilterUsed": bool(registered_names),
        "sourceImages": str(source_images),
        "colmapModel": str(colmap_model),
        "expectedCommand": "ns-train splatfacto --data <dataset_dir>",
    }
    (dataset_dir / "structura_dataset_manifest.json").write_text(json.dumps(adapter_metadata, indent=2), encoding="utf-8")
    visual_preview_repository.update_job_state(
        preview["visualPreviewId"],
        summary_json={
            "nerfstudioDatasetPath": str(dataset_dir),
            "nerfstudioDatasetImageCount": copied,
            "datasetReadiness": _dataset_files(dataset_dir),
        },
    )
    return dataset_dir


def _tail_log(path: str | None, line_count: int = LOG_TAIL_LINES) -> str:
    if not path:
        return ""
    log_path = Path(path)
    if not log_path.exists():
        return ""
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-line_count:])


def _training_command(ns_train: str, dataset_dir: Path, output_dir: Path, max_iterations: int) -> list[str]:
    return [
        ns_train,
        "splatfacto",
        "--output-dir",
        str(output_dir),
        "--vis",
        "tensorboard",
        "--max-num-iterations",
        str(max_iterations),
        "colmap",
        "--data",
        str(dataset_dir),
        "--colmap-path",
        str(Path("sparse") / "0"),
        "--downscale-factor",
        "1",
    ]


def _seconds_between(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    try:
        started = datetime.fromisoformat(start)
        finished = datetime.fromisoformat(end)
        return round((finished - started).total_seconds(), 2)
    except ValueError:
        return None


def _export_command(ns_export: str, config_path: str, export_dir: Path) -> list[str]:
    return [
        ns_export,
        "gaussian-splat",
        "--load-config",
        config_path,
        "--output-dir",
        str(export_dir),
    ]


def _find_latest_config(training_dir: Path) -> str | None:
    configs = sorted(training_dir.rglob("config.yml"), key=lambda path: path.stat().st_mtime, reverse=True)
    return str(configs[0]) if configs else None


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _splat_preview(project_id: str, visual_preview_id: str | None = None) -> dict[str, Any]:
    if not project_repository.get_project(project_id):
        raise VisualPreviewError("Project not found")
    preview = visual_preview_repository.get_visual_preview(visual_preview_id) if visual_preview_id else visual_preview_repository.latest_for_project(project_id)
    if not preview or preview.get("projectId") != project_id:
        raise VisualPreviewError("Visual preview manifest not found for this project.")
    return preview


def exported_splat_file(project_id: str, visual_preview_id: str | None = None) -> Path:
    preview = _splat_preview(project_id, visual_preview_id)
    splat_output_path = preview.get("splatOutputPath")
    if not splat_output_path:
        raise VisualPreviewError("Exported Gaussian Splat .ply was not found.")

    output_root = Path(preview["outputPath"]).resolve()
    processed_root = PROCESSED_DIR.resolve()
    splat_path = Path(str(splat_output_path)).resolve()
    if splat_path.suffix.lower() != ".ply":
        raise VisualPreviewError("Stored Gaussian Splat output is not a .ply file.")
    if not _is_relative_to(splat_path, output_root) or not _is_relative_to(splat_path, processed_root):
        raise VisualPreviewError("Stored Gaussian Splat output path is outside project storage.")
    if not splat_path.is_file():
        raise VisualPreviewError("Exported Gaussian Splat .ply was not found.")
    return splat_path


def exported_splat_metadata(project_id: str, visual_preview_id: str | None = None) -> dict[str, Any]:
    preview = _splat_preview(project_id, visual_preview_id)
    try:
        splat_path = exported_splat_file(project_id, visual_preview_id)
    except VisualPreviewError:
        return {
            "projectId": project_id,
            "visualPreviewId": preview.get("visualPreviewId"),
            "exists": False,
            "fileName": None,
            "fileSizeBytes": None,
            "createdAt": None,
            "modifiedAt": None,
            "relativePath": None,
            "downloadUrl": None,
        }

    stat = splat_path.stat()
    output_root = Path(preview["outputPath"]).resolve()
    return {
        "projectId": project_id,
        "visualPreviewId": preview.get("visualPreviewId"),
        "exists": True,
        "fileName": splat_path.name,
        "fileSizeBytes": stat.st_size,
        "createdAt": datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat(),
        "modifiedAt": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "relativePath": str(splat_path.relative_to(output_root)),
        "downloadUrl": f"/projects/{project_id}/visual-preview/splat-file?visual_preview_id={preview.get('visualPreviewId')}",
    }


def visual_preview_summary(project_id: str) -> dict[str, Any] | None:
    if not project_repository.get_project(project_id):
        return None
    reconstruction = reconstruction_service.reconstruction_summary(project_id)
    readiness = _readiness(project_id, reconstruction)
    latest = visual_preview_repository.latest_for_project(project_id)
    return {
        "projectId": project_id,
        "status": latest["status"] if latest else "not_started",
        "visualPreview": latest,
        "readiness": {key: value for key, value in readiness.items() if key != "attempt"},
        "sourceAttempt": readiness.get("attempt"),
        "nextStep": NEXT_STEP,
        "limitations": [
            "Visual reconstruction preview is intended for a more realistic browser-viewable scene. It is not a measurement-grade mesh.",
            "Full Gaussian Splat rendering is not implemented in this version.",
        ],
    }


def prepare_visual_preview(project_id: str, preview_type: str = DEFAULT_PREVIEW_TYPE) -> dict[str, Any]:
    if preview_type not in VISUAL_PREVIEW_TYPES:
        raise VisualPreviewError("Unsupported visual preview type.")
    if not project_repository.get_project(project_id):
        raise VisualPreviewError("Project not found")

    reconstruction = reconstruction_service.reconstruction_summary(project_id)
    readiness = _readiness(project_id, reconstruction)
    attempt = readiness.get("attempt")
    if not readiness["ready"] or not attempt:
        raise VisualPreviewError("; ".join(readiness["reasons"]) or "Visual preview is not ready to prepare.")

    visual_preview_id = str(uuid4())
    output_dir = PROCESSED_DIR / project_id / "visual_preview" / visual_preview_id
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"

    summary_json = {
        "projectId": project_id,
        "attemptId": attempt["attemptId"],
        "sourceAttemptId": attempt["attemptId"],
        "registeredImageCount": readiness["registeredImageCount"],
        "sparsePointCount": readiness["sparsePointCount"],
        "sparseQualityLabel": readiness["sparseQualityLabel"],
        "imageFolderPath": readiness["imageFolderPath"],
        "colmapModelPath": readiness["colmapModelPath"],
        "recommendedNextStep": NEXT_STEP,
        "limitations": [
            "This manifest prepares visual preview inputs only.",
            "Gaussian Splat training and rendering are not implemented in this version.",
        ],
    }
    manifest = {
        "visualPreviewId": visual_preview_id,
        "previewType": preview_type,
        **summary_json,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    visual_preview_repository.upsert_visual_preview(
        visual_preview_id=visual_preview_id,
        project_id=project_id,
        attempt_id=attempt["attemptId"],
        status="ready",
        preview_type=preview_type,
        source_attempt_id=attempt["attemptId"],
        output_path=str(output_dir),
        manifest_path=str(manifest_path),
        error_message=None,
        summary_json=summary_json,
    )
    summary = visual_preview_summary(project_id)
    if not summary:
        raise VisualPreviewError("Visual preview manifest was created, but summary could not be loaded.")
    return summary


def _run_training_job(visual_preview_id: str, command: list[str], log_path: Path, training_dir: Path) -> None:
    try:
        started_at = _now()
        visual_preview_repository.update_job_state(
            visual_preview_id,
            training_status="running",
            training_started_at=started_at,
            training_log_path=str(log_path),
            error_message=None,
            summary_json={"trainingCommand": command},
        )
        with log_path.open("a", encoding="utf-8", errors="replace") as log:
            log.write(f"Structura Visual Preview training command:\n{' '.join(command)}\n\n")
            log.flush()
            build_command, use_shell = _windows_build_command(command)
            result = subprocess.run(
                build_command,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_nerfstudio_subprocess_env(),
                shell=use_shell,
            )
        config_path = _find_latest_config(training_dir)
        finished_at = _now()
        if result.returncode != 0:
            visual_preview_repository.update_job_state(
                visual_preview_id,
                status="failed",
                training_status="failed",
                training_finished_at=finished_at,
                nerfstudio_config_path=config_path,
                error_message=f"Nerfstudio training failed with exit code {result.returncode}.",
                summary_json={"trainingDurationSeconds": _seconds_between(started_at, finished_at)},
            )
            return
        visual_preview_repository.update_job_state(
            visual_preview_id,
            status="ready",
            training_status="complete",
            training_finished_at=finished_at,
            nerfstudio_config_path=config_path,
            error_message=None,
            summary_json={"trainingDurationSeconds": _seconds_between(started_at, finished_at)},
        )
    except Exception as exc:
        visual_preview_repository.update_job_state(
            visual_preview_id,
            status="failed",
            training_status="failed",
            training_finished_at=_now(),
            error_message=str(exc),
        )


def train_visual_preview(
    project_id: str,
    *,
    visual_preview_id: str | None = None,
    attempt_id: str | None = None,
    max_iterations: int | None = None,
    preset: str = DEFAULT_TRAINING_PRESET,
) -> dict[str, Any]:
    diag = diagnostics()
    if not diag["nerfstudioAvailable"] or not diag["nsTrainPath"]:
        raise VisualPreviewError(diag["recommendedSetupMessage"])
    if preset not in TRAINING_PRESETS:
        raise VisualPreviewError("Preset must be smoke, quick, demo, or quality.")

    preview = visual_preview_repository.get_visual_preview(visual_preview_id) if visual_preview_id else visual_preview_repository.latest_for_project(project_id)
    if not preview:
        summary = prepare_visual_preview(project_id)
        preview = summary.get("visualPreview")
    if not preview or preview.get("projectId") != project_id:
        raise VisualPreviewError("Visual preview manifest not found for this project.")
    if attempt_id and preview.get("sourceAttemptId") != attempt_id:
        raise VisualPreviewError("The requested attempt does not match the selected visual preview manifest.")
    if preview.get("trainingStatus") in {"queued", "running"}:
        return training_status(project_id)

    iterations = max(1, int(max_iterations or TRAINING_PRESETS[preset]))
    dataset_dir = _prepare_nerfstudio_dataset(preview)
    dataset_readiness = _dataset_files(dataset_dir)
    if not dataset_readiness["ready"]:
        raise VisualPreviewError(f"Nerfstudio dataset is incomplete: {', '.join(dataset_readiness['missing'])}")
    output_dir = Path(preview["outputPath"]) / "nerfstudio_training"
    logs_dir = Path(preview["outputPath"]) / "logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "splatfacto_train.log"
    command = _training_command(str(diag["nsTrainPath"]), dataset_dir, output_dir, iterations)
    visual_preview_repository.update_job_state(
        preview["visualPreviewId"],
        status="ready",
        training_status="queued",
        export_status="not_started",
        training_log_path=str(log_path),
        error_message=None,
        summary_json={
            "trainingPreset": preset,
            "preset": preset,
            "maxIterations": iterations,
            "trainingCommand": command,
            "nerfstudioDatasetPath": str(dataset_dir),
            "datasetReadiness": dataset_readiness,
            "nerfstudioTrainingPath": str(output_dir),
        },
    )
    thread = threading.Thread(
        target=_run_training_job,
        args=(preview["visualPreviewId"], command, log_path, output_dir),
        daemon=True,
    )
    thread.start()
    return training_status(project_id)


def _run_export_command(preview: dict[str, Any], command: list[str], log_path: Path, export_dir: Path) -> dict[str, Any]:
    visual_preview_repository.update_job_state(
        preview["visualPreviewId"],
        export_status="running",
        export_log_path=str(log_path),
        error_message=None,
        summary_json={"exportCommand": command, "exportPath": str(export_dir)},
    )
    with log_path.open("a", encoding="utf-8", errors="replace") as log:
        log.write(f"Structura Visual Preview export command:\n{' '.join(command)}\n\n")
        log.flush()
        build_command, use_shell = _windows_build_command(command)
        result = subprocess.run(
            build_command,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_nerfstudio_subprocess_env(),
            shell=use_shell,
        )
    if result.returncode != 0:
        updated = visual_preview_repository.update_job_state(
            preview["visualPreviewId"],
            status="failed",
            export_status="failed",
            error_message=f"Nerfstudio export failed with exit code {result.returncode}.",
        )
        return training_status(preview["projectId"], updated)

    ply_outputs = [path for path in export_dir.rglob("*.ply") if path.is_file()]
    if not ply_outputs:
        updated = visual_preview_repository.update_job_state(
            preview["visualPreviewId"],
            status="failed",
            export_status="failed",
            error_message="Nerfstudio export finished, but no .ply Gaussian Splat file was found.",
        )
        return training_status(preview["projectId"], updated)
    splat_output = max(ply_outputs, key=lambda path: path.stat().st_mtime)
    splat_size = splat_output.stat().st_size
    updated = visual_preview_repository.update_job_state(
        preview["visualPreviewId"],
        status="ready",
        export_status="complete",
        splat_output_path=str(splat_output),
        splat_output_size_bytes=splat_size,
        viewer_asset_path=str(splat_output),
        error_message=None,
        summary_json={"splatOutputSizeBytes": splat_size},
    )
    return training_status(preview["projectId"], updated)


def export_visual_preview(project_id: str, visual_preview_id: str | None = None) -> dict[str, Any]:
    diag = diagnostics()
    if not diag["nerfstudioAvailable"] or not diag["nsExportPath"]:
        raise VisualPreviewError(diag["recommendedSetupMessage"])
    preview = visual_preview_repository.get_visual_preview(visual_preview_id) if visual_preview_id else visual_preview_repository.latest_for_project(project_id)
    if not preview or preview.get("projectId") != project_id:
        raise VisualPreviewError("Visual preview manifest not found for this project.")
    config_path = preview.get("nerfstudioConfigPath")
    if not config_path:
        raise VisualPreviewError("Nerfstudio config path is not available. Complete training before export.")
    export_dir = Path(preview["outputPath"]) / "exports"
    logs_dir = Path(preview["outputPath"]) / "logs"
    export_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "splatfacto_export.log"
    command = _export_command(str(diag["nsExportPath"]), config_path, export_dir)
    return _run_export_command(preview, command, log_path, export_dir)


def training_status(project_id: str, preview: dict[str, Any] | None = None) -> dict[str, Any]:
    if not project_repository.get_project(project_id):
        raise VisualPreviewError("Project not found")
    current = preview or visual_preview_repository.latest_for_project(project_id)
    summary_json = current.get("summaryJson") if current else {}
    return {
        "projectId": project_id,
        "visualPreviewId": current.get("visualPreviewId") if current else None,
        "status": current.get("status") if current else "not_started",
        "trainingStatus": current.get("trainingStatus") if current else "not_started",
        "exportStatus": current.get("exportStatus") if current else "not_started",
        "trainingStartedAt": current.get("trainingStartedAt") if current else None,
        "trainingFinishedAt": current.get("trainingFinishedAt") if current else None,
        "trainingLogPath": current.get("trainingLogPath") if current else None,
        "exportLogPath": current.get("exportLogPath") if current else None,
        "recentTrainingLog": _tail_log(current.get("trainingLogPath")) if current else "",
        "recentExportLog": _tail_log(current.get("exportLogPath")) if current else "",
        "nerfstudioConfigPath": current.get("nerfstudioConfigPath") if current else None,
        "splatOutputPath": current.get("splatOutputPath") if current else None,
        "splatOutputSizeBytes": current.get("splatOutputSizeBytes") if current else None,
        "viewerAssetPath": current.get("viewerAssetPath") if current else None,
        "errorMessage": current.get("errorMessage") if current else None,
        "trainingPreset": summary_json.get("trainingPreset") or summary_json.get("preset"),
        "maxIterations": summary_json.get("maxIterations"),
        "summaryJson": summary_json,
    }
