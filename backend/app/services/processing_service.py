from pathlib import Path
import shutil
import subprocess
from typing import Any

from PIL import Image

from app.database import PROCESSED_DIR, UPLOADS_DIR
from app.repositories import capture_repository, media_repository, project_repository

FPS_MODES = {
    "Fast": 1,
    "Balanced": 2,
    "Detailed": 3,
}
DEFAULT_FPS_MODE = "Balanced"
BLUR_SHARPNESS_THRESHOLD = 18.0
HIGH_BLUR_PERCENTAGE = 35.0

PIPELINE_STEPS = [
    "Upload received",
    "Extracting frames",
    "Preparing reconstruction workspace",
    "Capture analysis complete",
    "Ready for reconstruction",
]

VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}
NEXT_STEP = "reconstruction"


class ProcessingError(Exception):
    pass


def _project_workspace(project_id: str) -> dict[str, Path]:
    root = PROCESSED_DIR / project_id
    paths = {
        "root": root,
        "frames": root / "frames",
        "thumbnails": root / "thumbnails",
        "reconstruction": root / "reconstruction",
        "exports": root / "exports",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def _clear_frame_outputs(paths: dict[str, Path]) -> None:
    for folder_name in ("frames", "thumbnails"):
        folder = paths[folder_name]
        for item in folder.iterdir():
            if item.is_file():
                item.unlink()


def _ffmpeg_path() -> str | None:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _normalize_image(source: Path, target: Path) -> None:
    try:
        with Image.open(source) as image:
            image.convert("RGB").save(target, "JPEG", quality=92)
    except OSError as exc:
        raise ProcessingError(f"Unable to read uploaded image for frame extraction: {source.name}") from exc


def _thumbnail(source: Path, target: Path) -> None:
    try:
        with Image.open(source) as image:
            image.thumbnail((320, 220))
            image.convert("RGB").save(target, "JPEG", quality=82)
    except OSError as exc:
        raise ProcessingError(f"Unable to generate thumbnail for extracted frame: {source.name}") from exc


def normalize_fps_mode(mode: str | None) -> str:
    if not mode:
        return DEFAULT_FPS_MODE
    normalized = mode.strip().lower()
    for label in FPS_MODES:
        if normalized == label.lower():
            return label
    raise ProcessingError("Extraction FPS mode must be Fast, Balanced, or Detailed.")


def _extract_video_frames(video_path: Path, frames_dir: Path, start_index: int, fps: int) -> int:
    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        raise ProcessingError(
            "FFmpeg is required for video frame extraction. Install FFmpeg on PATH or install the backend dependency imageio-ffmpeg."
        )

    output_pattern = frames_dir / "frame_%04d.jpg"
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps}",
        "-start_number",
        str(start_index),
        str(output_pattern),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise ProcessingError(f"FFmpeg failed to extract frames: {result.stderr.strip() or result.stdout.strip()}")

    return len(list(frames_dir.glob("frame_*.jpg")))


def _sharpness_score(frame: Path) -> float | None:
    try:
        with Image.open(frame) as image:
            gray = image.convert("L")
            gray.thumbnail((240, 180))
            width, height = gray.size
            if width < 3 or height < 3:
                return None
            pixels = gray.load()
            values: list[float] = []
            for y in range(1, height - 1):
                for x in range(1, width - 1):
                    center = float(pixels[x, y])
                    laplacian = (4 * center) - float(pixels[x - 1, y]) - float(pixels[x + 1, y]) - float(pixels[x, y - 1]) - float(pixels[x, y + 1])
                    values.append(abs(laplacian))
            if not values:
                return None
            mean = sum(values) / len(values)
            variance = sum((value - mean) ** 2 for value in values) / len(values)
            return round(variance, 2)
    except OSError:
        return None


def _quality_metrics(frames: list[Path]) -> dict[str, Any]:
    scores = [score for frame in frames if (score := _sharpness_score(frame)) is not None]
    if not scores:
        return {
            "frameCount": len(frames),
            "averageSharpness": None,
            "blurryFrameCount": 0,
            "blurryFramePercentage": 0.0,
            "sharpnessAvailable": False,
        }

    blurry_count = sum(1 for score in scores if score < BLUR_SHARPNESS_THRESHOLD)
    blurry_percentage = round((blurry_count / len(scores)) * 100, 1)
    return {
        "frameCount": len(frames),
        "averageSharpness": round(sum(scores) / len(scores), 2),
        "blurryFrameCount": blurry_count,
        "blurryFramePercentage": blurry_percentage,
        "sharpnessAvailable": True,
    }


def _warnings(frame_count: int, image_count: int, video_count: int, blurry_percentage: float, sharpness_available: bool) -> list[str]:
    warnings: list[str] = []
    if frame_count < 30:
        warnings.append("Too few frames for reliable sparse reconstruction. Capture slower or use Detailed 3 FPS extraction.")
    elif 30 <= frame_count <= 80:
        warnings.append("Usable prototype capture, but more coverage may improve sparse reconstruction.")
    if video_count == 0 and image_count < 30:
        warnings.append("For reliable reconstruction, capture more overlapping images.")
    if sharpness_available and blurry_percentage >= HIGH_BLUR_PERCENTAGE:
        warnings.append("Many frames appear blurry. Move slower, improve lighting, or try Detailed 3 FPS extraction.")
    if frame_count < 30 or (sharpness_available and blurry_percentage >= HIGH_BLUR_PERCENTAGE):
        warnings.append("Low reconstruction confidence. Add overlap, texture, and slower camera motion before rerunning COLMAP.")
    if not sharpness_available and frame_count > 0:
        warnings.append("Sharpness analysis is unavailable for the extracted frames.")
    return warnings


def readiness_label(frame_count: int, blurry_percentage: float = 0.0) -> str:
    labels = ["Poor Capture", "Usable Prototype Capture", "Good Reconstruction Candidate"]
    if frame_count < 30:
        index = 0
    elif frame_count <= 80:
        index = 1
    else:
        index = 2
    if blurry_percentage >= HIGH_BLUR_PERCENTAGE:
        index = max(0, index - 1)
    return labels[index]


def start_processing(project_id: str, extraction_fps_mode: str | None = None) -> dict[str, Any] | None:
    project = project_repository.get_project(project_id)
    if not project:
        return None

    media = media_repository.list_media(project_id)
    if not media:
        raise ProcessingError("Upload at least one image or video before processing.")

    project_repository.set_processing(project_id)
    paths = _project_workspace(project_id)
    _clear_frame_outputs(paths)
    selected_fps_mode = normalize_fps_mode(extraction_fps_mode)
    extraction_fps = FPS_MODES[selected_fps_mode]

    frame_index = 1
    image_count = 0
    video_count = 0
    extraction_methods: set[str] = set()

    for item in media:
        source = UPLOADS_DIR / project_id / item["filename"]
        if not source.exists():
            raise ProcessingError(f"Uploaded media file is missing: {item['original_filename']}")

        if item["media_type"] == "image":
            target = paths["frames"] / f"frame_{frame_index:04d}.jpg"
            _normalize_image(source, target)
            image_count += 1
            frame_index += 1
            extraction_methods.add("image_upload")
        elif item["media_type"] == "video":
            suffix = source.suffix.lower()
            if suffix not in VIDEO_EXTENSIONS:
                raise ProcessingError("Video frame extraction supports .mp4, .mov, and .webm files.")
            before = len(list(paths["frames"].glob("frame_*.jpg")))
            after = _extract_video_frames(source, paths["frames"], frame_index, extraction_fps)
            extracted = after - before
            frame_index += extracted
            video_count += 1
            extraction_methods.add("ffmpeg")

    frames = sorted(paths["frames"].glob("frame_*.jpg"))
    for frame in frames:
        _thumbnail(frame, paths["thumbnails"] / frame.name)

    quality = _quality_metrics(frames)
    warning_list = _warnings(
        len(frames),
        image_count,
        video_count,
        float(quality["blurryFramePercentage"]),
        bool(quality["sharpnessAvailable"]),
    )
    extraction_method = "+".join(sorted(extraction_methods)) if extraction_methods else "none"

    capture = capture_repository.upsert_capture_metadata(
        project_id=project_id,
        uploaded_media_count=len(media),
        extracted_frame_count=len(frames),
        image_count=image_count,
        video_count=video_count,
        selected_fps_mode=selected_fps_mode,
        extraction_fps=extraction_fps,
        average_sharpness=quality["averageSharpness"],
        blurry_frame_count=quality["blurryFrameCount"],
        blurry_frame_percentage=quality["blurryFramePercentage"],
        sharpness_available=quality["sharpnessAvailable"],
        workspace_path=str(paths["root"]),
        extraction_method=extraction_method,
        warnings=warning_list,
        next_step=NEXT_STEP,
    )

    project_repository.set_ready(project_id)
    return get_status(project_id, capture)


def get_status(project_id: str, capture: dict[str, Any] | None = None) -> dict[str, Any] | None:
    project = project_repository.get_project(project_id)
    if not project:
        return None

    capture = capture if capture is not None else capture_repository.get_capture_metadata(project_id)
    capture_prepared = capture is not None

    return {
        "projectId": project_id,
        "status": project["status"],
        "progress": 100 if capture_prepared else 0,
        "currentStep": PIPELINE_STEPS[-1] if capture_prepared else PIPELINE_STEPS[0],
        "steps": PIPELINE_STEPS,
        "nextStep": NEXT_STEP if capture_prepared else None,
        "extractedFrameCount": capture["extracted_frame_count"] if capture else 0,
        "selectedFpsMode": capture["selected_fps_mode"] if capture else DEFAULT_FPS_MODE,
        "extractionFps": capture["extraction_fps"] if capture else FPS_MODES[DEFAULT_FPS_MODE],
        "averageSharpness": capture["average_sharpness"] if capture else None,
        "blurryFrameCount": capture["blurry_frame_count"] if capture else 0,
        "blurryFramePercentage": capture["blurry_frame_percentage"] if capture else 0,
        "sharpnessAvailable": capture["sharpness_available"] if capture else False,
        "warnings": capture["warnings"] if capture else [],
        "workspacePrepared": bool(capture),
        "readinessLabel": readiness_label(capture["extracted_frame_count"], capture["blurry_frame_percentage"]) if capture else "Poor Capture",
    }


def list_frames(project_id: str) -> list[dict[str, str]]:
    paths = _project_workspace(project_id)
    frames = sorted(paths["frames"].glob("frame_*.jpg"))
    return [
        {
            "filename": frame.name,
            "frameUrl": f"/processed-assets/{project_id}/frames/{frame.name}",
            "thumbnailUrl": f"/processed-assets/{project_id}/thumbnails/{frame.name}",
        }
        for frame in frames
    ]


def capture_summary(project_id: str) -> dict[str, Any] | None:
    project = project_repository.get_project(project_id)
    if not project:
        return None

    media = media_repository.list_media(project_id)
    capture = capture_repository.get_capture_metadata(project_id)
    if not capture:
        return {
            "projectId": project_id,
            "uploadedMediaCount": len(media),
            "extractedFrameCount": 0,
            "imageCount": sum(1 for item in media if item["media_type"] == "image"),
            "videoCount": sum(1 for item in media if item["media_type"] == "video"),
            "workspacePrepared": False,
            "workspacePath": None,
            "extractionMethod": None,
            "selectedFpsMode": DEFAULT_FPS_MODE,
            "extractionFps": FPS_MODES[DEFAULT_FPS_MODE],
            "averageSharpness": None,
            "blurryFrameCount": 0,
            "blurryFramePercentage": 0,
            "sharpnessAvailable": False,
            "warnings": [],
            "nextStep": None,
            "reconstructionReadiness": "Awaiting capture processing",
            "readinessLabel": "Poor Capture",
        }

    return {
        "projectId": project_id,
        "uploadedMediaCount": capture["uploaded_media_count"],
        "extractedFrameCount": capture["extracted_frame_count"],
        "imageCount": capture["image_count"],
        "videoCount": capture["video_count"],
        "workspacePrepared": True,
        "workspacePath": capture["workspace_path"],
        "extractionMethod": capture["extraction_method"],
        "selectedFpsMode": capture["selected_fps_mode"],
        "extractionFps": capture["extraction_fps"],
        "averageSharpness": capture["average_sharpness"],
        "blurryFrameCount": capture["blurry_frame_count"],
        "blurryFramePercentage": capture["blurry_frame_percentage"],
        "sharpnessAvailable": capture["sharpness_available"],
        "warnings": capture["warnings"],
        "nextStep": capture["next_step"],
        "reconstructionReadiness": "Ready for reconstruction pipeline",
        "readinessLabel": readiness_label(capture["extracted_frame_count"], capture["blurry_frame_percentage"]),
    }
