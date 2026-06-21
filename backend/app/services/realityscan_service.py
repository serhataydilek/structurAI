from pathlib import Path
from datetime import datetime, timezone
import os
import shutil
import subprocess
import threading
import time
from uuid import uuid4

from app.database import PROCESSED_DIR
from app.repositories import capture_repository, realityscan_job_repository
from app.repositories import project_repository
from app.services import job_progress_service, model_artifact_service

COMMON_EXECUTABLE_PATHS = (
    Path(r"C:\Program Files\Epic Games\RealityScan\RealityScan.exe"),
    Path(r"C:\Program Files\Epic Games\RealityScan_2.1\RealityScan.exe"),
)
DEFAULT_EXPORT_PARAMS_PATH = Path(__file__).resolve().parents[3] / "config" / "realityscan_export_obj.xml"
PROJECTS_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "projects"
JOB_KEY = "realityscan_prepare"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
PROGRESS_POLL_INTERVAL_SECONDS = 0.5
_ACTIVE_PROCESSES: dict[str, subprocess.Popen] = {}
_PROCESS_LOCK = threading.Lock()
_RUN_START_LOCK = threading.Lock()
ACTIVE_JOB_STATUSES = {"pending", "preparing", "running", "importing"}

# `-writeProgress` reports a separate 0..1 fraction for each RealityScan
# algorithm. These are observed task IDs for the command file generated below.
# Unknown IDs intentionally get a safe, explicit fallback rather than being
# treated as an overall percentage.
STAGES = {
    "preparing_images": (0.00, 0.08, "Preparing images"),
    "launching_realityscan": (0.08, 0.12, "Launching RealityScan"),
    "aligning_photos": (0.12, 0.35, "Aligning photos"),
    "selecting_component": (0.35, 0.40, "Selecting the best component"),
    "setting_region": (0.40, 0.45, "Setting the reconstruction region"),
    "reconstructing_mesh": (0.45, 0.70, "Reconstructing mesh"),
    "unwrapping": (0.70, 0.78, "Unwrapping mesh"),
    "texturing": (0.78, 0.94, "Texturing model"),
    "exporting_model": (0.94, 0.99, "Exporting RealityScan model"),
    "importing_artifact": (0.99, 1.00, "Importing model artifact"),
    "completed": (1.00, 1.00, "RealityScan model generation complete"),
    "failed": (0.00, 0.00, "RealityScan model generation failed"),
    "cancelled": (0.00, 0.00, "RealityScan model generation cancelled"),
}
ALG_STAGE_KEYS = {
    "65536": "launching_realityscan", "65537": "aligning_photos",
    "20534": "selecting_component", "20561": "reconstructing_mesh",
    "6": "reconstructing_mesh", "7": "unwrapping",
    "20533": "texturing", "21876": "exporting_model",
}


def _configured_path(env_var: str, fallback: Path | None = None) -> Path | None:
    configured = os.getenv(env_var)
    if configured:
        return Path(configured).expanduser()
    return fallback


def _executable_path() -> Path | None:
    configured = _configured_path("REALITYSCAN_EXE")
    if configured is not None:
        return configured
    return next((path for path in COMMON_EXECUTABLE_PATHS if path.is_file()), None)


def _export_params_path() -> Path | None:
    return _configured_path(
        "REALITYSCAN_EXPORT_PARAMS",
        DEFAULT_EXPORT_PARAMS_PATH if DEFAULT_EXPORT_PARAMS_PATH.is_file() else None,
    )


def diagnostics() -> dict:
    executable_path = _executable_path()
    export_params_path = _export_params_path()
    executable_exists = executable_path.is_file() if executable_path else False
    export_params_exists = export_params_path.is_file() if export_params_path else False
    enabled = os.getenv("STRUCTURA_ENABLE_REALITYSCAN", "").lower() == "true"

    notes = ["No RealityScan process was started."]
    if not enabled:
        notes.append("RealityScan integration is disabled. Set STRUCTURA_ENABLE_REALITYSCAN=true to enable it.")
    if not executable_exists:
        notes.append("RealityScan executable was not found. Set REALITYSCAN_EXE or install RealityScan in a supported location.")
    if not export_params_exists:
        notes.append(
            "RealityScan OBJ export parameters were not found. Set REALITYSCAN_EXPORT_PARAMS or add config/realityscan_export_obj.xml generated from RealityScan's Export Model dialog."
        )

    return {
        "available": executable_exists and export_params_exists,
        "enabled": enabled,
        "executable_path": str(executable_path) if executable_path else None,
        "executable_exists": executable_exists,
        "export_params_path": str(export_params_path) if export_params_path else None,
        "export_params_exists": export_params_exists,
        "headless_supported": "unknown",
        "notes": notes,
    }


def _validated_images(project_id: str) -> list[Path]:
    capture_job = job_progress_service.get(project_id, "capture_processing")
    if capture_job and capture_job.get("status") == "running":
        raise ValueError("Waiting for capture processing to finish.")

    capture = capture_repository.get_capture_metadata(project_id)
    if not capture or int(capture["extracted_frame_count"]) <= 0:
        raise ValueError("Waiting for validated images.")

    frames_dir = PROCESSED_DIR / project_id / "frames"
    images = sorted(path for path in frames_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS) if frames_dir.is_dir() else []
    if len(images) < 20:
        raise ValueError("At least 20 validated images are required.")
    return images


def _rscmd_contents(images_dir: Path, job_dir: Path, export_dir: Path, export_params_path: Path) -> str:
    return "\n".join(
        (
            "-newScene",
            f'-addFolder "{images_dir}"',
            "-align",
            "-selectMaximalComponent",
            "-setReconstructionRegionAuto",
            "-calculateNormalModel",
            "-unwrap",
            "-calculateTexture",
            f'-save "{job_dir / "project.rsproj"}"',
            f'-exportSelectedModel "{export_dir / "model.obj"}" "{export_params_path}"',
            "-quit",
            "",
        )
    )


def parse_progress_file(progress_file_path: str | Path) -> dict | None:
    try:
        lines = Path(progress_file_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    for line in reversed(lines):
        values = line.split()
        if len(values) < 5:
            continue
        try:
            alg_id = str(int(values[0]))
            progress = float(values[1])
            elapsed_seconds = float(values[2])
            eta_seconds = float(values[3])
        except ValueError:
            continue
        if not 0 <= progress <= 1 or elapsed_seconds < 0 or eta_seconds < 0:
            continue
        stage_key = ALG_STAGE_KEYS.get(alg_id, "launching_realityscan")
        start, end, label = STAGES[stage_key]
        return {
            "raw_progress": progress,
            "raw_elapsed_seconds": elapsed_seconds,
            "raw_eta_seconds": eta_seconds,
            "alg_id": alg_id,
            "progress": start + (end - start) * progress,
            "event_type": values[4],
            "stage_key": stage_key,
            "stage_label": label if alg_id in ALG_STAGE_KEYS else "RealityScan task in progress",
        }
    return None


def _stable_eta(job: dict, progress: dict) -> float | None:
    # RealityScan's ETA is task-local and wildly unstable at task start. Use a
    # wall-clock overall estimate only after enough work has completed.
    overall = progress["progress"]
    started_at = job.get("started_at")
    if overall < 0.15 or not started_at:
        return None
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        elapsed = max(0.0, (datetime.now(timezone.utc) - started).total_seconds())
    except ValueError:
        return None
    if elapsed < 20:
        return None
    estimate = elapsed * (1 - overall) / overall
    previous = job.get("eta_seconds")
    # Limit each refresh to a modest adjustment, avoiding stage-boundary jumps.
    if previous is not None:
        estimate = max(float(previous) * 0.75, min(float(previous) * 1.25, estimate))
    return round(estimate)


def _refresh_job_progress(job_id: str, progress_file_path: str | Path | None) -> None:
    if not progress_file_path:
        return
    progress = parse_progress_file(progress_file_path)
    if progress:
        job = realityscan_job_repository.get_job(job_id) or {}
        realityscan_job_repository.update_job_progress(
            job_id,
            progress["progress"],
            elapsed_seconds=progress["raw_elapsed_seconds"],
            eta_seconds=_stable_eta(job, progress),
            stage=progress["stage_key"],
            raw_progress=progress["raw_progress"], raw_eta_seconds=progress["raw_eta_seconds"],
            raw_elapsed_seconds=progress["raw_elapsed_seconds"], raw_alg_id=progress["alg_id"],
        )


def prepare_dry_run(project_id: str, *, dry_run: bool = True) -> dict:
    if not dry_run:
        raise ValueError("RealityScan execution is not supported yet; dry_run must be true")

    images = _validated_images(project_id)
    job_id = str(uuid4())
    job_dir = PROJECTS_DATA_DIR / project_id / "realityscan" / job_id
    images_dir = job_dir / "images"
    export_dir = job_dir / "export"
    crash_dir = job_dir / "crash"
    logs_dir = job_dir / "logs"
    progress_file_path = logs_dir / "progress.txt"
    rscmd_path = job_dir / "job.rscmd"
    project_file_path = job_dir / "project.rsproj"
    exported_model_path = export_dir / "model.obj"

    for directory in (images_dir, export_dir, crash_dir, logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    for image in images:
        shutil.copy2(image, images_dir / image.name)

    export_params_path = _export_params_path() or DEFAULT_EXPORT_PARAMS_PATH
    rscmd_path.write_text(
        _rscmd_contents(images_dir, job_dir, export_dir, export_params_path),
        encoding="utf-8",
    )

    executable_path = _executable_path()
    command_preview = [
        str(executable_path) if executable_path else "RealityScan.exe",
        "-headless",
        "-silent",
        str(crash_dir),
        "-set",
        "appQuitOnError=true",
        "-writeProgress",
        str(progress_file_path),
        "2",
        "-execRSCMD",
        str(rscmd_path),
    ]
    job = realityscan_job_repository.create_job(
        project_id,
        str(job_dir),
        job_id=job_id,
        status="pending",
        stage="prepared",
        image_count=len(images),
        images_dir=str(images_dir),
        export_dir=str(export_dir),
        progress_file_path=str(progress_file_path),
        project_file_path=str(project_file_path),
        exported_model_path=str(exported_model_path),
    )
    return {
        "job_id": job["id"],
        "project_id": job["project_id"],
        "dry_run": True,
        "status": "prepared",
        "image_count": job["image_count"],
        "job_dir": job["job_dir"],
        "rscmd_path": str(rscmd_path),
        "progress_file_path": job["progress_file_path"],
        "exported_model_path": job["exported_model_path"],
        "command_preview": command_preview,
    }


def _validate_runtime_configuration() -> None:
    diagnostic = diagnostics()
    errors = []
    if not diagnostic["enabled"]:
        errors.append("STRUCTURA_ENABLE_REALITYSCAN=true is required")
    if not diagnostic["executable_exists"]:
        errors.append("RealityScan executable was not found")
    if not diagnostic["export_params_exists"]:
        errors.append("RealityScan export parameters XML was not found")
    if errors:
        raise ValueError("; ".join(errors))


def _run_background_job(
    job_id: str,
    command: list[str],
    job_dir: Path,
    stdout_path: Path,
    stderr_path: Path,
    progress_file_path: Path,
    exported_model_path: Path,
) -> None:
    process: subprocess.Popen | None = None
    started_at = time.monotonic()
    try:
        realityscan_job_repository.update_job_status(job_id, "preparing", stage="launching_realityscan")
        with stdout_path.open("w", encoding="utf-8") as stdout_log, stderr_path.open("w", encoding="utf-8") as stderr_log:
            process = subprocess.Popen(
                command,
                cwd=job_dir,
                stdout=stdout_log,
                stderr=stderr_log,
            )
            with _PROCESS_LOCK:
                _ACTIVE_PROCESSES[job_id] = process
            realityscan_job_repository.update_job_status(job_id, "running", stage="launching_realityscan")
            while process.poll() is None:
                _refresh_job_progress(job_id, progress_file_path)
                time.sleep(PROGRESS_POLL_INTERVAL_SECONDS)
            return_code = process.wait()
            _refresh_job_progress(job_id, progress_file_path)

        job = realityscan_job_repository.get_job(job_id)
        if job and job["status"] == "cancelled":
            return
        if return_code != 0:
            realityscan_job_repository.mark_job_failed(job_id, f"RealityScan exited with code {return_code}")
            return
        if not exported_model_path.is_file():
            realityscan_job_repository.mark_job_failed(
                job_id,
                f"RealityScan completed but exported model was not found: {exported_model_path}",
            )
            return

        elapsed_seconds = time.monotonic() - started_at
        realityscan_job_repository.update_job_status(job_id, "importing", stage="importing_artifact")
        realityscan_job_repository.update_job_progress(job_id, 1.0, elapsed_seconds=elapsed_seconds, stage="importing_artifact")
        model_artifact_service.register_realityscan_export(job["project_id"], job_id, exported_model_path)
        realityscan_job_repository.mark_job_completed(job_id, exported_model_path=str(exported_model_path))
    except Exception as exc:
        job = realityscan_job_repository.get_job(job_id)
        if not job or job["status"] != "cancelled":
            realityscan_job_repository.mark_job_failed(job_id, f"RealityScan runner failed: {exc}")
    finally:
        if process is not None:
            with _PROCESS_LOCK:
                if _ACTIVE_PROCESSES.get(job_id) is process:
                    _ACTIVE_PROCESSES.pop(job_id, None)


def run(project_id: str, *, dry_run: bool) -> dict:
    if dry_run:
        return prepare_dry_run(project_id)

    # Serialise starts so repeated clicks or requests cannot prepare two jobs.
    with _RUN_START_LOCK:
        existing_job = realityscan_job_repository.get_latest_job_for_project(project_id)
        if existing_job and existing_job["status"] in ACTIVE_JOB_STATUSES:
            job_dir = Path(existing_job["job_dir"])
            return {
                "job_id": existing_job["id"],
                "project_id": existing_job["project_id"],
                "dry_run": False,
                "status": existing_job["status"],
                "image_count": existing_job["image_count"],
                "job_dir": existing_job["job_dir"],
                "rscmd_path": str(job_dir / "job.rscmd"),
                "progress_file_path": existing_job["progress_file_path"],
                "exported_model_path": existing_job["exported_model_path"],
                "command_preview": [],
            }

        _validate_runtime_configuration()
        prepared = prepare_dry_run(project_id)
        job_id = prepared["job_id"]
        job_dir = Path(prepared["job_dir"])
        logs_dir = job_dir / "logs"
        thread = threading.Thread(
            target=_run_background_job,
            args=(
                job_id,
                prepared["command_preview"],
                job_dir,
                logs_dir / "realityscan_stdout.log",
                logs_dir / "realityscan_stderr.log",
                Path(prepared["progress_file_path"]),
                Path(prepared["exported_model_path"]),
            ),
            name=f"realityscan-{job_id}",
            daemon=True,
        )
        thread.start()
        return {
            **prepared,
            "dry_run": False,
            "status": "running",
        }


def latest_status(project_id: str) -> dict | None:
    job = realityscan_job_repository.get_latest_job_for_project(project_id)
    if not job:
        return None
    if job["status"] == "running":
        _refresh_job_progress(job["id"], job["progress_file_path"])
        job = realityscan_job_repository.get_job(job["id"]) or job

    progress = job["progress"]
    project = project_repository.get_project(project_id) or {}
    stage_key = job["status"] if job["status"] in {"completed", "failed", "cancelled"} else (job["stage"] or "launching_realityscan")
    stage_label = STAGES.get(stage_key, (0, 0, "RealityScan model generation"))[2]
    return {
        "job_id": job["id"],
        "run_id": job["id"],
        "project_name": project.get("name"),
        "status": job["status"],
        "stage": job["stage"],
        "stage_key": stage_key,
        "stage_label": stage_label,
        "progress": progress,
        "progress_percent": round(progress * 100) if progress is not None else None,
        "elapsed_seconds": job["elapsed_seconds"],
        "eta_seconds": job["eta_seconds"],
        "stable_eta_seconds": job["eta_seconds"],
        "raw_progress_percent": round(job["raw_progress"] * 100) if job.get("raw_progress") is not None else None,
        "started_at": job.get("started_at"),
        "updated_at": job.get("updated_at"),
        "image_count": job["image_count"],
        "error_message": job["error_message"],
    }


def cancel_latest_job(project_id: str) -> dict:
    job = realityscan_job_repository.get_latest_job_for_project(project_id)
    if not job:
        return {
            "cancelled": False,
            "message": "No RealityScan job exists for this project",
        }

    with _PROCESS_LOCK:
        process = _ACTIVE_PROCESSES.get(job["id"])
    if process is None or process.poll() is not None:
        return {
            "job_id": job["id"],
            "cancelled": False,
            "status": job["status"],
            "message": "Cancellation is unsupported because no active RealityScan process handle is available",
        }

    try:
        process.terminate()
    except OSError as exc:
        return {
            "job_id": job["id"],
            "cancelled": False,
            "status": job["status"],
            "message": f"RealityScan process could not be terminated: {exc}",
        }

    realityscan_job_repository.update_job_status(job["id"], "cancelled", stage="cancellation_requested")
    return {
        "job_id": job["id"],
        "cancelled": True,
        "status": "cancelled",
    }


def prepare(project_id: str) -> dict:
    frames=PROCESSED_DIR/project_id/"frames"; images=[p for p in frames.glob("*") if p.suffix.lower() in IMAGE_EXTENSIONS] if frames.is_dir() else []
    if len(images)<3: raise ValueError("At least three prepared images are required for a RealityScan job")
    job_progress_service.start(project_id, JOB_KEY, "copying_images", f"Copying RealityScan image set: 0/{len(images)}", total_items=len(images), progress_percent=5)
    job_root=PROCESSED_DIR/project_id/"realityscan_jobs"; temp_id=__import__("uuid").uuid4().hex
    root=job_root/temp_id; input_dir=root/"input"; output=root/"output"; logs=root/"logs"
    for directory in (input_dir,output,logs): directory.mkdir(parents=True,exist_ok=True)
    try:
        for index,image in enumerate(images, start=1):
            shutil.copy2(image, input_dir / image.name)
            job_progress_service.update(project_id, JOB_KEY, label=f"Copied image {index}/{len(images)}", progress_percent=5 + index / max(len(images),1) * 75, processed_items=index, total_items=len(images))
        job_progress_service.update(project_id, JOB_KEY, stage="writing_command_draft", label="Writing RealityScan manual workflow draft", progress_percent=90, processed_items=None, total_items=None)
        command=root/"realityscan_command_draft.txt"; diag=diagnostics()
        command.write_text("RealityScan automation draft\nInput folder: %s\nOutput folder: %s\nTODO: verify this RealityScan version's command-file/headless syntax before executing.\nManual bridge: import images, align, build model, texture, export OBJ + MTL + textures as ZIP.\n"%(input_dir,output),encoding="utf-8")
        ready = diag["available"] and diag["enabled"]
        job = realityscan_job_repository.create_job(
            project_id,
            str(root),
            image_count=len(images),
            images_dir=str(input_dir),
            export_dir=str(output),
            progress_file_path=str(logs / "progress.txt"),
            project_file_path=str(root / "project.rsproj"),
            exported_model_path=str(output / "model.obj"),
            stage="prepared",
        )
        job_progress_service.complete(project_id, JOB_KEY, f"RealityScan job prepared with {len(images)} images", warnings=diag["notes"])
        return {**job,"diagnostics":diag,"ready":ready,"manualRequired":not ready,"progress":job_progress_service.get(project_id, JOB_KEY)}
    except Exception as exc:
        job_progress_service.fail(project_id, JOB_KEY, str(exc))
        raise
