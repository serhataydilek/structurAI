from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from app.repositories import annotation_repository, capture_repository, media_repository, project_repository, reconstruction_repository
from app.database import get_connection
from app.services import reconstruction_service, visual_preview_service
from app.services.processing_service import readiness_label


def _preview_mode(project: dict[str, Any], capture: dict[str, Any] | None, summary: dict[str, Any] | None = None) -> str:
    attempt_mode = (summary or {}).get("displayedAttempt", {}).get("viewerPreviewMode") or (summary or {}).get("bestAttempt", {}).get("viewerPreviewMode")
    if attempt_mode == "exterior":
        return "exterior"
    if attempt_mode == "interior":
        return "interior"
    if project.get("scan_type") == "Building Scan":
        return "exterior"
    if capture and int(capture.get("image_count") or 0) >= 40 and int(capture.get("video_count") or 0) == 0:
        return "exterior"
    return "interior"


def _detected_output(summary: dict[str, Any] | None, preview_mode: str = "interior") -> str:
    mode = summary["currentBestViewerMode"] if summary else "prototype_preview"
    if mode == "dense_point_cloud":
        return "Dense point cloud preview"
    if summary and summary.get("sparsePointCloudAvailable"):
        if preview_mode == "exterior":
            return "Sparse building point cloud preview"
        points = int(summary.get("sparsePointCount") or summary.get("pointCount") or 0)
        if summary.get("sparseQualityLabel") == "Poor Sparse Reconstruction" or points < 1500:
            return "Weak sparse reconstruction preview"
        return "Sparse scene preview"
    return "No reconstruction output"


def _limitations(summary: dict[str, Any] | None, preview_mode: str = "interior") -> list[str]:
    if summary and summary.get("currentBestViewerMode") == "dense_point_cloud":
        return [
            "Dense point cloud reconstruction is enabled. Mesh generation and GLB export are not yet implemented.",
            "Measurements are approximate in this prototype.",
        ]
    if summary and summary.get("sparsePointCloudAvailable"):
        if preview_mode == "exterior":
            return [
                "COLMAP reconstruction has arbitrary scale and orientation unless aligned manually.",
                "This is a sparse point cloud, not a dense mesh.",
                "Measurements are approximate in this prototype.",
            ]
        return [
            "Sparse reconstruction is enabled and has generated matched 3D feature points. The preview combines sparse COLMAP points with estimated room bounds.",
            "Room bounds and floor level are estimated from sparse features, not measured geometry or a generated mesh.",
            "Measurements are approximate in this prototype.",
        ]
    return [
        "No reconstructed point cloud is available yet. Upload media, process capture, then run sparse reconstruction to generate a real preview.",
        "Measurements are approximate in this prototype.",
    ]


def _report_next_action(summary: dict[str, Any] | None) -> str:
    if not summary:
        return "Run sparse reconstruction"
    if not summary.get("sparsePointCloudAvailable"):
        return "Run sparse reconstruction"
    if summary.get("denseStatus") == "Dense Reconstruction Failed" and summary.get("denseReconstructionLikelyAvailable") is False:
        return "Install a CUDA-enabled COLMAP build or use a visual preview pipeline"
    if summary.get("sparseQualityLabel") == "Poor Sparse Reconstruction":
        return "Improve capture and rerun sparse reconstruction"
    if summary.get("denseReconstructionLikelyAvailable") is False:
        return "Continue sparse scene preview or install CUDA-enabled COLMAP"
    if summary.get("denseStatus") in {"Dense Reconstruction Not Started", "Dense Reconstruction Running"}:
        return "Run dense reconstruction"
    if summary.get("denseReadiness", {}).get("ready"):
        return "Run dense reconstruction"
    return summary.get("recommendedNextAction") or "Run sparse reconstruction"


def _attempt_display_status(attempt: dict[str, Any]) -> str:
    status = str(attempt.get("status") or "")
    if "Failed" in status:
        return "Failed"
    if int(attempt.get("registeredImageCount") or 0) <= 0 or int(attempt.get("sparsePointCount") or 0) <= 0:
        return "No points"
    return "Complete"


def _with_attempt_display_status(attempt: dict[str, Any]) -> dict[str, Any]:
    item = dict(attempt)
    item["attemptDisplayStatus"] = _attempt_display_status(item)
    return item


def _visual_preview_report_status(visual_preview_summary: dict[str, Any] | None) -> str:
    preview = (visual_preview_summary or {}).get("visualPreview") or {}
    if not preview:
        return "Not prepared"
    if preview.get("status") == "failed" or preview.get("trainingStatus") == "failed" or preview.get("exportStatus") == "failed":
        return "Failed"
    if preview.get("exportStatus") == "complete":
        return "Export ready"
    if preview.get("trainingStatus") == "complete":
        return "Training complete"
    if preview.get("trainingStatus") in {"queued", "running"}:
        return "Training running"
    if visual_preview_summary and visual_preview_summary.get("status") == "ready":
        return "Manifest ready"
    return "Not prepared"


def _visual_preview_report_note(visual_preview_summary: dict[str, Any] | None) -> str:
    status = _visual_preview_report_status(visual_preview_summary)
    if status == "Export ready":
        return "Gaussian Splat export is ready. In-browser splat rendering will be added next."
    if status == "Training complete":
        return "Nerfstudio Splatfacto training completed; export is available next."
    if status == "Training running":
        return "Nerfstudio Splatfacto training is running in the background."
    if status == "Manifest ready":
        return "Visual preview inputs prepared from the best sparse attempt."
    if status == "Failed":
        return "Visual preview training or export failed. Review logs and diagnostics."
    return "Visual preview manifest has not been prepared."


def _split_attempts(attempts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    successful: list[dict[str, Any]] = []
    failed_or_empty: list[dict[str, Any]] = []
    for attempt in attempts:
        item = _with_attempt_display_status(attempt)
        if item["attemptDisplayStatus"] == "Complete":
            successful.append(item)
        else:
            failed_or_empty.append(item)
    return successful, failed_or_empty


def _viewer_orientation_aligned(attempt: dict[str, Any] | None) -> bool:
    if not attempt:
        return False
    transform = attempt.get("viewerTransform") or {}
    return any([
        int(transform.get("rotationX") or 0) % 360 != 0,
        int(transform.get("rotationY") or 0) % 360 != 0,
        int(transform.get("rotationZ") or 0) % 360 != 0,
        bool(transform.get("flipX")),
        bool(transform.get("flipY")),
        bool(transform.get("flipZ")),
        float(transform.get("scale") or 1) != 1,
        float(transform.get("offsetX") or 0) != 0,
        float(transform.get("offsetY") or 0) != 0,
        float(transform.get("offsetZ") or 0) != 0,
    ])


def _summary_scene_analysis(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if not summary:
        return None
    attempt = summary.get("displayedAttempt") or summary.get("bestAttempt") or summary.get("latestAttempt")
    scene = (attempt or {}).get("sceneAnalysisSummary") or {}
    return scene if scene else None


def _cache_key(
    project: dict[str, Any],
    capture: dict[str, Any] | None,
    annotations: list[dict[str, Any]],
    reconstruction_summary: dict[str, Any] | None,
    visual_preview_summary: dict[str, Any] | None,
    media_count: int,
) -> str:
    attempts = reconstruction_summary.get("reconstructionAttempts", []) if reconstruction_summary else []
    payload = {
        "project": {
            "id": project.get("id"),
            "name": project.get("name"),
            "siteType": project.get("site_type"),
            "description": project.get("description"),
            "scanType": project.get("scan_type"),
            "status": project.get("status"),
            "processingStartedAt": project.get("processing_started_at"),
        },
        "capture": capture,
        "mediaCount": media_count,
        "annotations": [
            {"id": item.get("id"), "text": item.get("text"), "createdAt": item.get("created_at")}
            for item in annotations
        ],
        "reconstruction": {
            "status": (reconstruction_summary or {}).get("status"),
            "sparseStatus": (reconstruction_summary or {}).get("sparseStatus"),
            "denseStatus": (reconstruction_summary or {}).get("denseStatus"),
            "bestAttemptId": ((reconstruction_summary or {}).get("bestAttempt") or {}).get("attemptId"),
            "latestAttemptId": ((reconstruction_summary or {}).get("latestAttempt") or {}).get("attemptId"),
            "displayedAttemptId": ((reconstruction_summary or {}).get("displayedAttempt") or {}).get("attemptId"),
            "attempts": [
                {
                    "attemptId": item.get("attemptId"),
                    "status": item.get("status"),
                    "registered": item.get("registeredImageCount"),
                    "selected": item.get("selectedFrameCount"),
                    "source": item.get("sourceFrameCount"),
                    "points": item.get("sparsePointCount"),
                    "quality": item.get("sparseQualityLabel"),
                    "isBest": item.get("isBestAttempt"),
                    "viewerTransform": item.get("viewerTransform"),
                    "viewerPreviewMode": item.get("viewerPreviewMode"),
                    "sceneAnalysisSummary": item.get("sceneAnalysisSummary"),
                }
                for item in attempts
            ],
            "denseLogs": (reconstruction_summary or {}).get("denseLogPreviewSummary"),
            "denseError": (reconstruction_summary or {}).get("denseErrorMessage"),
        },
            "visualPreview": {
            "status": (visual_preview_summary or {}).get("status"),
            "visualPreviewId": (((visual_preview_summary or {}).get("visualPreview") or {}).get("visualPreviewId")),
            "manifestPath": (((visual_preview_summary or {}).get("visualPreview") or {}).get("manifestPath")),
            "sourceAttemptId": (((visual_preview_summary or {}).get("visualPreview") or {}).get("sourceAttemptId")),
            "trainingStatus": (((visual_preview_summary or {}).get("visualPreview") or {}).get("trainingStatus")),
            "exportStatus": (((visual_preview_summary or {}).get("visualPreview") or {}).get("exportStatus")),
            "splatOutputPath": (((visual_preview_summary or {}).get("visualPreview") or {}).get("splatOutputPath")),
            "readiness": (visual_preview_summary or {}).get("readiness"),
        },
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _get_cached_report(project_id: str, cache_key: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT report_json FROM report_cache WHERE project_id = ? AND cache_key = ?",
            (project_id, cache_key),
        ).fetchone()
    if not row:
        return None
    return json.loads(row["report_json"])


def _store_cached_report(project_id: str, cache_key: str, report: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO report_cache (project_id, cache_key, report_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                cache_key = excluded.cache_key,
                report_json = excluded.report_json,
                updated_at = excluded.updated_at
            """,
            (project_id, cache_key, json.dumps(report), now, now),
        )


def build_report(project_id: str) -> dict[str, Any] | None:
    project = project_repository.get_project(project_id)
    if not project:
        return None

    annotations = annotation_repository.list_annotations(project_id)
    media = media_repository.list_media(project_id)
    capture = capture_repository.get_capture_metadata(project_id)
    reconstruction = reconstruction_repository.get_reconstruction_metadata(project_id)
    reconstruction_summary = reconstruction_service.reconstruction_summary(project_id)
    visual_preview = visual_preview_service.visual_preview_summary(project_id)
    cache_key = _cache_key(project, capture, annotations, reconstruction_summary, visual_preview, len(media))
    cached = _get_cached_report(project_id, cache_key)
    if cached:
        cached["reportCacheStatus"] = "hit"
        return cached

    scene_analysis = _summary_scene_analysis(reconstruction_summary)
    preview_mode = _preview_mode(project, capture, reconstruction_summary)
    attempts = reconstruction_summary["reconstructionAttempts"] if reconstruction_summary else []
    successful_attempts, failed_or_empty_attempts = _split_attempts(attempts)
    best_attempt = reconstruction_summary["bestAttempt"] if reconstruction_summary else None
    displayed_attempt = reconstruction_summary["displayedAttempt"] if reconstruction_summary else None
    report: dict[str, Any] = {
        "projectName": project["name"],
        "projectId": project_id,
        "uploadedMediaCount": len(media),
        "processingStatus": project["status"],
        "detectedOutput": _detected_output(reconstruction_summary, preview_mode),
        "captureMetadata": {
            "uploadedMediaCount": capture["uploaded_media_count"] if capture else len(media),
            "extractedFrameCount": capture["extracted_frame_count"] if capture else 0,
            "imageCount": capture["image_count"] if capture else sum(1 for item in media if item["media_type"] == "image"),
            "videoCount": capture["video_count"] if capture else sum(1 for item in media if item["media_type"] == "video"),
            "workspacePrepared": bool(capture),
            "workspacePath": capture["workspace_path"] if capture else None,
            "extractionMethod": capture["extraction_method"] if capture else None,
            "selectedFpsMode": capture["selected_fps_mode"] if capture else "Balanced",
            "extractionFps": capture["extraction_fps"] if capture else 2,
            "averageSharpness": capture["average_sharpness"] if capture else None,
            "blurryFrameCount": capture["blurry_frame_count"] if capture else 0,
            "blurryFramePercentage": capture["blurry_frame_percentage"] if capture else 0,
            "sharpnessAvailable": capture["sharpness_available"] if capture else False,
            "warnings": capture["warnings"] if capture else [],
            "nextStep": capture["next_step"] if capture else None,
            "readinessLabel": readiness_label(capture["extracted_frame_count"], capture["blurry_frame_percentage"]) if capture else "Poor Capture",
        },
        "warnings": capture["warnings"] if capture else [],
        "reconstructionMetadata": {
            "status": reconstruction_summary["sparseStatus"] if reconstruction_summary else "Not Started",
            "sparseStatus": reconstruction_summary["sparseStatus"] if reconstruction_summary else "Not Started",
            "denseStatus": reconstruction_summary["denseStatus"] if reconstruction_summary else "Dense Reconstruction Not Started",
            "inputFrameCount": reconstruction_summary["inputFrameCount"] if reconstruction_summary else 0,
            "selectedFpsMode": reconstruction_summary["selectedFpsMode"] if reconstruction_summary else "Balanced",
            "extractionFps": reconstruction_summary["extractionFps"] if reconstruction_summary else 2,
            "matchingMode": reconstruction_summary["matchingMode"] if reconstruction_summary else "Auto",
            "matchingModeUsed": reconstruction_summary["matchingModeUsed"] if reconstruction_summary else "Not Started",
            "sparseOutputExists": reconstruction_summary["sparseOutputExists"] if reconstruction_summary else False,
            "sparsePointCloudAvailable": reconstruction_summary["sparsePointCloudAvailable"] if reconstruction_summary else False,
            "densePointCloudAvailable": reconstruction_summary["densePointCloudAvailable"] if reconstruction_summary else False,
            "pointCount": reconstruction_summary["pointCount"] if reconstruction_summary else 0,
            "sparsePointCount": reconstruction_summary["sparsePointCount"] if reconstruction_summary else 0,
            "registeredImageCount": reconstruction_summary["registeredImageCount"] if reconstruction_summary else 0,
            "registrationRatio": reconstruction_summary["registrationRatio"] if reconstruction_summary else 0,
            "registrationRatioLabel": reconstruction_summary["registrationRatioLabel"] if reconstruction_summary else "No extracted frames",
            "selectedRegistrationRatio": reconstruction_summary["selectedRegistrationRatio"] if reconstruction_summary else 0,
            "sourceRegistrationRatio": reconstruction_summary["sourceRegistrationRatio"] if reconstruction_summary else 0,
            "sourceRegistrationRatioLabel": reconstruction_summary["sourceRegistrationRatioLabel"] if reconstruction_summary else "No source frames",
            "sourceFrameCount": reconstruction_summary["sourceFrameCount"] if reconstruction_summary else 0,
            "selectedFrameCount": reconstruction_summary["selectedFrameCount"] if reconstruction_summary else 0,
            "frameSelectionMode": reconstruction_summary["frameSelectionMode"] if reconstruction_summary else "Balanced subset",
            "selectedFrameFolder": reconstruction_summary["selectedFrameFolder"] if reconstruction_summary else None,
            "sparseQualityLabel": reconstruction_summary["sparseQualityLabel"] if reconstruction_summary else "Not evaluated",
            "sparseReconstructionQuality": reconstruction_summary["sparseReconstructionQuality"] if reconstruction_summary else "Not evaluated",
            "reconstructionAttempts": [_with_attempt_display_status(attempt) for attempt in attempts],
            "successfulAttempts": successful_attempts,
            "failedOrEmptyAttempts": failed_or_empty_attempts,
            "hiddenFailedAttemptCount": len(failed_or_empty_attempts),
            "bestAttempt": best_attempt,
            "latestAttempt": reconstruction_summary["latestAttempt"] if reconstruction_summary else None,
            "displayedAttempt": displayed_attempt,
            "displayedAttemptRole": reconstruction_summary["displayedAttemptRole"] if reconstruction_summary else None,
            "denseReadiness": reconstruction_summary["denseReadiness"] if reconstruction_summary else {"ready": False, "recommended": False, "reasons": ["sparse reconstruction is not complete"]},
            "visualPreviewStatus": visual_preview["status"] if visual_preview else "not_started",
            "visualPreviewReadiness": visual_preview["readiness"] if visual_preview else {"ready": False, "recommended": False, "reasons": ["project not found"]},
            "visualPreview": visual_preview["visualPreview"] if visual_preview else None,
            "visualPreviewReportStatus": _visual_preview_report_status(visual_preview),
            "visualPreviewReportNote": _visual_preview_report_note(visual_preview),
            "densePointCount": reconstruction_summary["densePointCount"] if reconstruction_summary else 0,
            "colmapAvailable": reconstruction_summary["colmapAvailable"] if reconstruction_summary else False,
            "colmapPath": reconstruction_summary["colmapPath"] if reconstruction_summary else None,
            "colmapVersion": reconstruction_summary["colmapVersion"] if reconstruction_summary else None,
            "colmapCudaHint": reconstruction_summary["colmapCudaHint"] if reconstruction_summary else None,
            "denseReconstructionLikelyAvailable": reconstruction_summary["denseReconstructionLikelyAvailable"] if reconstruction_summary else "unknown",
            "viewerModeRecommendation": reconstruction_summary["viewerModeRecommendation"] if reconstruction_summary else "prototype_preview",
            "currentBestViewerMode": reconstruction_summary["currentBestViewerMode"] if reconstruction_summary else "prototype_preview",
            "previewMode": preview_mode,
            "viewerOrientationAlignedManually": _viewer_orientation_aligned(displayed_attempt or best_attempt),
            "sparseModelFolders": reconstruction_summary["sparseModelFolders"] if reconstruction_summary else [],
            "sceneAnalysis": scene_analysis,
            "denseLogPreviewSummary": reconstruction_summary["denseLogPreviewSummary"] if reconstruction_summary else {},
            "warnings": reconstruction_summary["warnings"] if reconstruction_summary else [],
            "errorMessage": reconstruction_summary["errorMessage"] if reconstruction_summary else None,
            "denseWarnings": reconstruction_summary["denseWarnings"] if reconstruction_summary else [],
            "denseErrorMessage": reconstruction_summary["denseErrorMessage"] if reconstruction_summary else None,
            "likelyCauses": reconstruction_summary["likelyCauses"] if reconstruction_summary else [],
            "denseLikelyCauses": reconstruction_summary["denseLikelyCauses"] if reconstruction_summary else [],
            "lowRegistrationRecommendations": reconstruction_summary["lowRegistrationRecommendations"] if reconstruction_summary else [],
            "recommendedFixes": reconstruction_summary["recommendedFixes"] if reconstruction_summary else [],
            "recommendedNextAction": _report_next_action(reconstruction_summary),
            "nextStep": "Dense reconstruction / point cloud visualization",
        },
        "annotations": annotations,
        "limitations": [
            *_limitations(reconstruction_summary, preview_mode),
            "Full Gaussian Splat rendering is not implemented in this version.",
            "Visual preview is optimized for viewing, not measurement-grade geometry.",
        ],
    }
    _store_cached_report(project_id, cache_key, report)
    report["reportCacheStatus"] = "miss"
    return report
