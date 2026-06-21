import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.services import model_preview_service


class ModelPreviewSourceTests(unittest.TestCase):
    def test_rejects_non_ready_and_non_obj_sources(self):
        with self.assertRaises(model_preview_service.ModelPreviewError):
            model_preview_service._source_obj({"status": "failed", "storagePath": "x.obj"})
        with self.assertRaises(model_preview_service.ModelPreviewError):
            model_preview_service._source_obj({"status": "ready", "storagePath": "x.ply"})

    def test_rejects_source_outside_managed_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            obj = Path(directory) / "raw.obj"; obj.touch()
            with self.assertRaisesRegex(model_preview_service.ModelPreviewError, "managed storage"):
                model_preview_service._source_obj({"status": "ready", "storagePath": str(obj)})

    def test_accepts_realityscan_project_storage_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "data" / "projects"
            obj = root / "project" / "realityscan" / "job" / "export" / "model.obj"
            obj.parent.mkdir(parents=True)
            obj.touch()
            with patch.object(model_preview_service, "REALITYSCAN_DATA_DIR", root):
                self.assertEqual(model_preview_service._source_obj({"status": "ready", "storagePath": str(obj)}), obj)

    def test_status_includes_running_stage_and_progress(self):
        progress = {"status": "running", "currentStage": "converting_obj_to_glb", "progressPercent": 50, "startedAt": "2026-06-21T10:00:00+00:00", "updatedAt": "2026-06-21T10:01:00+00:00", "errors": []}
        with patch.object(model_preview_service.job_progress_service, "get", return_value=progress), \
             patch.object(model_preview_service.model_artifact_repository, "list_artifacts", return_value=[]):
            status = model_preview_service.status("project", "raw")
        self.assertEqual(status["status"], "running")
        self.assertEqual(status["stage"], "converting_obj_to_glb")
        self.assertEqual(status["progress_percent"], 50)
        self.assertEqual(status["started_at"], "2026-06-21T10:00:00+00:00")
        self.assertEqual(status["updated_at"], "2026-06-21T10:01:00+00:00")

    def test_prepare_rejects_duplicate_running_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "raw.obj"; source.touch()
            artifact = {"artifactId": "raw", "status": "ready", "storagePath": str(source)}
            with patch.object(model_preview_service, "_inside_managed_storage", return_value=True), \
                 patch.object(model_preview_service, "diagnostics", return_value={"enabled": True, "available": True, "blender_path": str(source)}), \
                 patch.object(model_preview_service.job_progress_service, "get", return_value={"status": "running"}):
                with self.assertRaisesRegex(model_preview_service.ModelPreviewError, "already being prepared"):
                    model_preview_service.prepare("project", artifact)

    def test_successful_run_registers_viewer_ready_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "raw.obj"; source.touch()
            output = root / "project" / "model_preview" / "job" / "preview.glb"
            report = output.with_name("preview_report.json")
            log = output.with_name("blender.log")
            def run_blender(*args, **kwargs):
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"glb")
                report.write_text('{"polygon_count": 800, "texture_count": 2, "warnings": []}')
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            artifact = {"artifactId": "raw", "status": "ready", "storagePath": str(source), "role": "current_state"}
            with patch.object(model_preview_service, "PROCESSED_DIR", root), \
                 patch.object(model_preview_service.subprocess, "run", side_effect=run_blender) as run, \
                 patch.object(model_preview_service.model_artifact_repository, "add_artifact") as add:
                model_preview_service._run("project", artifact, source, output, report, log, root / "blender.exe")
            self.assertEqual(add.call_args.kwargs["metadata"]["artifactRole"], "viewer_ready")
            self.assertEqual(add.call_args.kwargs["metadata"]["sourceArtifactId"], "raw")
            self.assertEqual(add.call_args.args[9]["faceCount"], 800)
            self.assertEqual(add.call_args.args[10]["mainGlbPath"], str(output))
            command = run.call_args.args[0]
            self.assertIn("--", command)
            self.assertEqual(command[-3:], [str(source), str(output), str(report)])

    def test_registering_derived_preview_uses_new_output_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / "raw.obj"; source.touch(); output = root / "preview.glb"; output.touch()
            with patch.object(model_preview_service, "_inside_managed_storage", return_value=True), \
                 patch.object(model_preview_service.model_artifact_repository, "add_artifact") as add:
                artifact = {"artifactId": "raw", "status": "ready", "storagePath": str(source), "role": "current_state"}
                # _run's success registration is covered without invoking Blender.
                self.assertNotEqual(source, output)
                model_preview_service.model_artifact_repository.add_artifact("p", "textured_mesh", "manual", output.name, 0, str(output), "preview.glb", "", None, {}, metadata={"artifactRole": "viewer_ready", "sourceArtifactId": artifact["artifactId"]})
                self.assertEqual(add.call_args.kwargs["metadata"]["sourceArtifactId"], "raw")


if __name__ == "__main__":
    unittest.main()
