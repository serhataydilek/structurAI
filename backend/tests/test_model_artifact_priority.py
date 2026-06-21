import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app import main
from app.services import model_artifact_service, model_postprocessing_service


def artifact(role: str, *, format: str | None = None, source: str = "realityscan", file_size: int = 1024, face_count: int = 1000):
    model_format = format or ("glb" if role == "viewer_ready" else "obj")
    return {"artifactId": role, "artifactType": "textured_mesh", "sourceTool": source, "source_type": source, "role": None,
            "status": "ready", "artifactRole": role, "format": model_format, "storagePath": f"missing.{model_format}", "bundle": {},
            "fileSize": file_size, "stats": {"faceCount": face_count}}


class ModelArtifactPriorityTests(unittest.TestCase):
    def test_summary_prefers_viewer_ready_then_cleaned_then_raw(self):
        artifacts = [artifact("raw_realityscan"), artifact("cleaned_mesh"), artifact("viewer_ready")]
        with patch.object(model_artifact_service.model_artifact_repository, "list_artifacts", return_value=artifacts), \
             patch.object(model_artifact_service.model_artifact_repository, "list_comparisons", return_value=[]), \
             patch.object(model_artifact_service, "_is_gaussian_splat", return_value=False):
            self.assertEqual(model_artifact_service.summary("project")["preferredModelArtifact"]["artifactRole"], "viewer_ready")

    def test_summary_uses_first_latest_viewer_ready_artifact(self):
        older = artifact("viewer_ready"); older["artifactId"] = "older"
        latest = artifact("viewer_ready"); latest["artifactId"] = "latest"
        with patch.object(model_artifact_service.model_artifact_repository, "list_artifacts", return_value=[latest, older, artifact("raw_realityscan")]), \
             patch.object(model_artifact_service.model_artifact_repository, "list_comparisons", return_value=[]), \
             patch.object(model_artifact_service, "_is_gaussian_splat", return_value=False):
            self.assertEqual(model_artifact_service.summary("project")["preferredModelArtifact"]["artifactId"], "latest")

    def test_summary_skips_oversized_viewer_ready_artifact(self):
        oversized = artifact("viewer_ready", file_size=300 * 1024 * 1024, face_count=1000)
        raw = artifact("raw_realityscan")
        with patch.object(model_artifact_service.model_artifact_repository, "list_artifacts", return_value=[oversized, raw]), \
             patch.object(model_artifact_service.model_artifact_repository, "list_comparisons", return_value=[]), \
             patch.object(model_artifact_service, "_is_gaussian_splat", return_value=False):
            self.assertEqual(model_artifact_service.summary("project")["preferredModelArtifact"]["artifactRole"], "raw_realityscan")

    def test_no_preferred_artifact_when_no_renderable_artifact_exists(self):
        with patch.object(model_artifact_service.model_artifact_repository, "list_artifacts", return_value=[artifact("raw_realityscan", format="ply")]), \
             patch.object(model_artifact_service.model_artifact_repository, "list_comparisons", return_value=[]), \
             patch.object(model_artifact_service, "_is_gaussian_splat", return_value=False):
            self.assertIsNone(model_artifact_service.summary("project")["preferredModelArtifact"])

    def test_derived_registration_rejects_raw_path_and_leaves_raw_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "raw.obj"; raw.write_text("raw geometry")
            source = {"artifactId": "raw-id", "storagePath": str(raw)}
            with self.assertRaisesRegex(ValueError, "must not overwrite"):
                model_postprocessing_service.register_derived_artifact("project", source, storage_path=str(raw))
            self.assertEqual(raw.read_text(), "raw geometry")


class ViewerAssetServingTests(unittest.TestCase):
    def test_serves_file_inside_managed_bundle_only(self):
        with tempfile.TemporaryDirectory() as directory:
            processed = Path(directory) / "processed"; bundle = processed / "project" / "bundle"; bundle.mkdir(parents=True)
            obj = bundle / "model.obj"; obj.write_text("v 0 0 0")
            record = {"storagePath": str(obj), "primary_file_path": str(obj), "bundle": {"bundleRootPath": str(bundle)}}
            with patch.object(main, "PROCESSED_DIR", processed), patch.object(main.model_artifact_repository, "get_artifact", return_value=record):
                response = main.model_artifact_viewer_file("project", "artifact", "model.obj")
            self.assertEqual(Path(response.path), obj)

    def test_rejects_bundle_path_traversal_and_missing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            processed = Path(directory) / "processed"; bundle = processed / "project" / "bundle"; bundle.mkdir(parents=True)
            obj = bundle / "model.obj"; obj.touch(); (processed / "secret.txt").write_text("secret")
            record = {"storagePath": str(obj), "primary_file_path": str(obj), "bundle": {"bundleRootPath": str(bundle)}}
            with patch.object(main, "PROCESSED_DIR", processed), patch.object(main.model_artifact_repository, "get_artifact", return_value=record):
                with self.assertRaises(HTTPException) as traversal:
                    main.model_artifact_viewer_file("project", "artifact", "../secret.txt")
                with self.assertRaises(HTTPException) as missing:
                    main.model_artifact_viewer_file("project", "artifact", "missing.mtl")
            self.assertEqual(traversal.exception.status_code, 404)
            self.assertEqual(missing.exception.status_code, 404)

    def test_rejects_artifact_paths_outside_managed_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "outside"; outside.mkdir(); obj = outside / "model.obj"; obj.touch()
            record = {"storagePath": str(obj), "primary_file_path": str(obj), "bundle": {"bundleRootPath": str(outside)}}
            with patch.object(main, "PROCESSED_DIR", Path(directory) / "processed"), patch.object(main.model_artifact_repository, "get_artifact", return_value=record):
                with self.assertRaises(HTTPException) as result:
                    main.model_artifact_viewer_file("project", "artifact", "model.obj")
            self.assertEqual(result.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
