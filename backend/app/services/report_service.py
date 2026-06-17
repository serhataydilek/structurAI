from typing import Any

from app.repositories import annotation_repository, capture_repository, media_repository, project_repository, reconstruction_repository
from app.services import reconstruction_service
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


def build_report(project_id: str) -> dict[str, Any] | None:
    project = project_repository.get_project(project_id)
    if not project:
        return None

    annotations = annotation_repository.list_annotations(project_id)
    media = media_repository.list_media(project_id)
    capture = capture_repository.get_capture_metadata(project_id)
    reconstruction = reconstruction_repository.get_reconstruction_metadata(project_id)
    reconstruction_summary = reconstruction_service.reconstruction_summary(project_id)
    scene_analysis = reconstruction_service.scene_analysis(project_id) if reconstruction_summary and reconstruction_summary.get("sparsePointCloudAvailable") else None
    preview_mode = _preview_mode(project, capture, reconstruction_summary)

    return {
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
            "reconstructionAttempts": reconstruction_summary["reconstructionAttempts"] if reconstruction_summary else [],
            "bestAttempt": reconstruction_summary["bestAttempt"] if reconstruction_summary else None,
            "latestAttempt": reconstruction_summary["latestAttempt"] if reconstruction_summary else None,
            "displayedAttempt": reconstruction_summary["displayedAttempt"] if reconstruction_summary else None,
            "displayedAttemptRole": reconstruction_summary["displayedAttemptRole"] if reconstruction_summary else None,
            "denseReadiness": reconstruction_summary["denseReadiness"] if reconstruction_summary else {"ready": False, "recommended": False, "reasons": ["sparse reconstruction is not complete"]},
            "densePointCount": reconstruction_summary["densePointCount"] if reconstruction_summary else 0,
            "colmapAvailable": reconstruction_summary["colmapAvailable"] if reconstruction_summary else False,
            "colmapPath": reconstruction_summary["colmapPath"] if reconstruction_summary else None,
            "colmapVersion": reconstruction_summary["colmapVersion"] if reconstruction_summary else None,
            "colmapCudaHint": reconstruction_summary["colmapCudaHint"] if reconstruction_summary else None,
            "denseReconstructionLikelyAvailable": reconstruction_summary["denseReconstructionLikelyAvailable"] if reconstruction_summary else "unknown",
            "viewerModeRecommendation": reconstruction_summary["viewerModeRecommendation"] if reconstruction_summary else "prototype_preview",
            "currentBestViewerMode": reconstruction_summary["currentBestViewerMode"] if reconstruction_summary else "prototype_preview",
            "previewMode": preview_mode,
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
        "limitations": _limitations(reconstruction_summary, preview_mode),
    }
