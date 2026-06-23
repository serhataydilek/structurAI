import tempfile
import time
import unittest
import json
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import database, main
from app.repositories import model_artifact_repository
from app.services import model_artifact_service


class TargetModelApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [
            patch.object(database, "STORAGE_DIR", root),
            patch.object(database, "UPLOADS_DIR", root / "uploads"),
            patch.object(database, "PROCESSED_DIR", root / "processed"),
            patch.object(database, "DB_PATH", root / "structura.db"),
            patch.object(main, "PROCESSED_DIR", root / "processed"),
            patch.object(model_artifact_service, "PROCESSED_DIR", root / "processed"),
        ]
        for item in self.patches:
            item.start()
        database.init_db()
        self.client_context = TestClient(main.app)
        self.client = self.client_context.__enter__()
        self.project_id = self.client.post("/projects", json={"name": "Target test", "siteType": "Office", "description": ""}).json()["id"]

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        # Windows can retain SQLite's file handle briefly after the ASGI test portal closes.
        for _ in range(10):
            try:
                self.temp.cleanup()
                break
            except PermissionError:
                time.sleep(0.05)

    def upload(self, name: str, content: bytes):
        return self.client.post(f"/projects/{self.project_id}/target-model", files={"file": (name, content)})

    def download_latest_delivery_package(self):
        generated = self.client.post(f"/projects/{self.project_id}/delivery-packages")
        self.assertEqual(generated.status_code, 201)
        return self.client.get(f"/projects/{self.project_id}/delivery-package.zip")

    def generated_artifact(self, project_id: str | None = None, *, name: str = "current.glb", content: bytes = b"glTF\x02\x00\x00\x00", role: str = "viewer_ready"):
        project_id = project_id or self.project_id
        root = database.PROCESSED_DIR / project_id / "model_artifacts"
        root.mkdir(parents=True, exist_ok=True)
        path = root / name
        path.write_bytes(content)
        suffix = path.suffix.lower()
        bundle = {"mainGlbPath": str(path)} if suffix == ".glb" else {"mainObjPath": str(path)}
        return model_artifact_repository.add_artifact(
            project_id, "mesh", "manual", name, path.stat().st_size, str(path), str(path.relative_to(database.PROCESSED_DIR)),
            "Generated model", None, {}, bundle, model_format=suffix.lstrip("."), primary_file_path=str(path), status="ready",
            metadata={"artifactRole": role},
        )

    def test_uploads_glb_as_target_artifact(self):
        response = self.upload("final.glb", b"glTF\x02\x00\x00\x00")
        self.assertEqual(response.status_code, 200)
        artifact = response.json()
        self.assertEqual(artifact["artifactRole"], "target_model")
        self.assertEqual(artifact["format"], "glb")
        self.assertEqual(artifact["id"], artifact["artifactId"])
        self.assertEqual(artifact["filename"], "final.glb")
        self.assertEqual(artifact["sizeBytes"], len(b"glTF\x02\x00\x00\x00"))
        self.assertIn("downloadUrl", artifact)
        self.assertEqual(self.client.get(artifact["fileUrl"]).status_code, 200)

    def test_uploads_obj_as_target_artifact(self):
        response = self.upload("final.obj", b"v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["artifactRole"], "target_model")
        self.assertEqual(response.json()["format"], "obj")

    def test_rejects_invalid_extension(self):
        response = self.upload("final.ply", b"ply")
        self.assertEqual(response.status_code, 400)
        self.assertIn(".glb and .obj", response.json()["detail"])

    def test_get_returns_latest_target_artifact(self):
        first = self.upload("first.obj", b"v 0 0 0\n").json()
        latest = self.upload("latest.glb", b"glTF\x02\x00\x00\x00").json()
        response = self.client.get(f"/projects/{self.project_id}/target-model")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["artifactId"], latest["artifactId"])
        self.assertNotEqual(response.json()["artifactId"], first["artifactId"])

    def test_delete_existing_target_model_removes_file_and_current_target(self):
        artifact = self.upload("final.obj", b"v 0 0 0\n").json()
        self.assertEqual(self.client.delete(f"/projects/{self.project_id}/target-model").json()["deleted"], True)
        self.assertIsNone(self.client.get(f"/projects/{self.project_id}/target-model").json())
        self.assertEqual(self.client.get(artifact["fileUrl"]).status_code, 404)

    def test_delete_without_target_model_is_safe(self):
        response = self.client.delete(f"/projects/{self.project_id}/target-model")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["deleted"])

    def test_replacement_keeps_only_newest_target_active(self):
        self.upload("first.obj", b"v 0 0 0\n")
        latest = self.upload("latest.glb", b"glTF\x02\x00\x00\x00").json()
        self.assertEqual(self.client.get(f"/projects/{self.project_id}/target-model").json()["artifactId"], latest["artifactId"])

    def test_promotes_specific_generated_glb_without_mutating_source(self):
        source = self.generated_artifact()
        response = self.client.post(f"/projects/{self.project_id}/target-model/promote", json={"artifactId": source["artifactId"]})
        self.assertEqual(response.status_code, 200)
        promoted = response.json()
        self.assertEqual(promoted["artifactRole"], "target_model")
        self.assertEqual(promoted["format"], "glb")
        self.assertNotEqual(promoted["artifactId"], source["artifactId"])
        unchanged = model_artifact_repository.get_artifact(self.project_id, source["artifactId"])
        self.assertEqual(unchanged["artifactRole"], "viewer_ready")
        self.assertTrue(Path(unchanged["storagePath"]).is_file())
        self.assertEqual(model_artifact_repository.get_latest_ready_artifact(self.project_id)["artifactId"], source["artifactId"])

    def test_latest_generated_model_includes_viewer_metadata(self):
        source = self.generated_artifact()
        response = self.client.get(f"/projects/{self.project_id}/model-artifacts/latest")
        self.assertEqual(response.status_code, 200)
        artifact = response.json()
        self.assertEqual(artifact["id"], source["artifactId"])
        self.assertEqual(artifact["filename"], source["fileName"])
        self.assertEqual(artifact["sizeBytes"], source["fileSize"])
        self.assertIn("fileUrl", artifact)

    def test_promotes_latest_generated_model_when_artifact_id_omitted(self):
        source = self.generated_artifact(name="latest.obj", content=b"v 0 0 0\n", role="raw_realityscan")
        response = self.client.post(f"/projects/{self.project_id}/target-model/promote", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sourceArtifactId"], source["artifactId"])

    def test_promotion_supersedes_previous_active_target(self):
        previous = self.upload("previous.obj", b"v 0 0 0\n").json()
        source = self.generated_artifact()
        promoted = self.client.post(f"/projects/{self.project_id}/target-model/promote", json={"artifactId": source["artifactId"]}).json()
        self.assertEqual(self.client.get(f"/projects/{self.project_id}/target-model").json()["artifactId"], promoted["artifactId"])
        self.assertEqual(model_artifact_repository.get_artifact(self.project_id, previous["artifactId"])["status"], "superseded")

    def test_promotion_rejects_unsupported_format(self):
        source = self.generated_artifact(name="current.ply", content=b"ply", role="raw_realityscan")
        response = self.client.post(f"/projects/{self.project_id}/target-model/promote", json={"artifactId": source["artifactId"]})
        self.assertEqual(response.status_code, 400)
        self.assertIn(".glb and .obj", response.json()["detail"])

    def test_promotion_rejects_artifact_from_another_project(self):
        other_id = self.client.post("/projects", json={"name": "Other", "siteType": "Office", "description": ""}).json()["id"]
        foreign = self.generated_artifact(other_id)
        response = self.client.post(f"/projects/{self.project_id}/target-model/promote", json={"artifactId": foreign["artifactId"]})
        self.assertEqual(response.status_code, 404)

    def test_promotion_rejects_an_existing_target_model(self):
        target = self.upload("final.obj", b"v 0 0 0\n").json()
        response = self.client.post(f"/projects/{self.project_id}/target-model/promote", json={"artifactId": target["artifactId"]})
        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot be promoted again", response.json()["detail"])

    def test_final_model_is_not_ready_without_an_active_target(self):
        response = self.client.get(f"/projects/{self.project_id}/final-model")
        self.assertEqual(response.json(), {"ready": False, "model": None, "reason": "No target model has been uploaded or promoted yet."})

    def test_final_model_reflects_uploaded_target_and_deletion(self):
        uploaded = self.upload("final.obj", b"v 0 0 0\n").json()
        final = self.client.get(f"/projects/{self.project_id}/final-model").json()
        self.assertTrue(final["ready"])
        self.assertEqual(final["model"]["artifactId"], uploaded["artifactId"])
        self.assertEqual(final["model"]["source"], "uploaded")
        self.client.delete(f"/projects/{self.project_id}/target-model")
        self.assertFalse(self.client.get(f"/projects/{self.project_id}/final-model").json()["ready"])

    def test_final_model_reflects_promoted_and_replaced_target(self):
        source = self.generated_artifact()
        promoted = self.client.post(f"/projects/{self.project_id}/target-model/promote", json={"artifactId": source["artifactId"]}).json()
        final = self.client.get(f"/projects/{self.project_id}/final-model").json()
        self.assertEqual(final["model"]["artifactId"], promoted["artifactId"])
        self.assertEqual(final["model"]["source"], "promoted")
        replacement = self.upload("replacement.obj", b"v 0 0 0\n").json()
        self.assertEqual(self.client.get(f"/projects/{self.project_id}/final-model").json()["model"]["artifactId"], replacement["artifactId"])

    def test_final_model_preflight_reports_missing_model(self):
        preflight = self.client.get(f"/projects/{self.project_id}/final-model/preflight").json()
        self.assertEqual(preflight["status"], "missing")
        self.assertFalse(preflight["finalModel"]["exists"])
        self.assertFalse(preflight["packageReady"])
        self.assertIn("No target model", preflight["blockers"][0])

    def test_final_model_preflight_reports_ready_uploaded_glb(self):
        uploaded = self.upload("final.glb", b"glTF\x02\x00\x00\x00").json()
        preflight = self.client.get(f"/projects/{self.project_id}/final-model/preflight").json()
        self.assertEqual(preflight["status"], "ready")
        self.assertTrue(preflight["packageReady"])
        self.assertEqual(preflight["finalModel"]["artifactId"], uploaded["artifactId"])
        self.assertEqual(preflight["finalModel"]["format"], "glb")
        self.assertEqual(preflight["finalModel"]["source"], "uploaded")
        self.assertIsNone(preflight["bundle"])
        self.assertIsNone(preflight["thumbnail"])

    def test_final_model_preflight_warns_for_standalone_obj(self):
        self.upload("final.obj", b"v 0 0 0\n")
        preflight = self.client.get(f"/projects/{self.project_id}/final-model/preflight").json()
        self.assertEqual(preflight["status"], "warning")
        self.assertTrue(preflight["packageReady"])
        self.assertEqual(preflight["finalModel"]["format"], "obj")
        self.assertEqual(preflight["bundle"], {"mtlFiles": [], "textureFiles": [], "hasMtl": False, "hasTextures": False, "supportedForPackaging": True})
        self.assertIsNone(preflight["thumbnail"])
        self.assertTrue(any("standalone" in warning for warning in preflight["warnings"]))

    def test_final_model_preflight_detects_glb_thumbnail_sidecar(self):
        uploaded = self.upload("final.glb", b"glTF\x02\x00\x00\x00").json()
        model_path = Path(uploaded["primary_file_path"])
        thumbnail = model_path.with_name(f"{model_path.stem}.thumbnail.png")
        thumbnail.write_bytes(b"png")
        preflight = self.client.get(f"/projects/{self.project_id}/final-model/preflight").json()
        self.assertEqual(preflight["thumbnail"], {
            "exists": True, "filename": thumbnail.name, "format": "png", "sizeBytes": 3,
            "source": "final_model_sidecar", "supportedForPackaging": True,
            "fileUrl": f"/projects/{self.project_id}/model-artifacts/{uploaded['artifactId']}/viewer-files/{thumbnail.name}",
        })

    def test_final_model_preflight_detects_obj_thumbnail_sidecar(self):
        uploaded = self.upload("final.obj", b"v 0 0 0\n").json()
        model_path = Path(uploaded["primary_file_path"])
        thumbnail = model_path.with_name(f"{model_path.stem}.thumbnail.jpg")
        thumbnail.write_bytes(b"jpg")
        preflight = self.client.get(f"/projects/{self.project_id}/final-model/preflight").json()
        self.assertEqual(preflight["thumbnail"]["format"], "jpg")
        self.assertEqual(preflight["thumbnail"]["filename"], thumbnail.name)

    def test_final_model_preflight_thumbnail_uses_png_priority(self):
        uploaded = self.upload("final.glb", b"glTF\x02\x00\x00\x00").json()
        model_path = Path(uploaded["primary_file_path"])
        png = model_path.with_name(f"{model_path.stem}.thumbnail.png")
        model_path.with_name(f"{model_path.stem}.thumbnail.webp").write_bytes(b"webp")
        png.write_bytes(b"png")
        preflight = self.client.get(f"/projects/{self.project_id}/final-model/preflight").json()
        self.assertEqual(preflight["thumbnail"]["filename"], png.name)

    def test_final_model_preflight_ignores_wrong_stem_and_thumbnail_directory(self):
        uploaded = self.upload("final.obj", b"v 0 0 0\n").json()
        model_path = Path(uploaded["primary_file_path"])
        (model_path.parent / "other.thumbnail.png").write_bytes(b"png")
        model_path.with_name(f"{model_path.stem}.thumbnail.webp").mkdir()
        preflight = self.client.get(f"/projects/{self.project_id}/final-model/preflight").json()
        self.assertIsNone(preflight["thumbnail"])

    def test_final_model_preflight_detects_obj_mtl_companion(self):
        uploaded = self.upload("final.obj", b"v 0 0 0\n").json()
        model_path = Path(uploaded["primary_file_path"])
        (model_path.parent / "final.mtl").write_text("newmtl material\n")
        preflight = self.client.get(f"/projects/{self.project_id}/final-model/preflight").json()
        self.assertTrue(preflight["bundle"]["hasMtl"])
        self.assertEqual(preflight["bundle"]["mtlFiles"], ["final.mtl"])
        self.assertTrue(preflight["bundle"]["supportedForPackaging"])
        self.assertEqual(preflight["warnings"], [])

    def test_final_model_preflight_detects_obj_texture_companion(self):
        uploaded = self.upload("final.obj", b"v 0 0 0\n").json()
        model_path = Path(uploaded["primary_file_path"])
        (model_path.parent / "albedo.png").write_bytes(b"png")
        preflight = self.client.get(f"/projects/{self.project_id}/final-model/preflight").json()
        self.assertTrue(preflight["bundle"]["hasTextures"])
        self.assertEqual(preflight["bundle"]["textureFiles"], ["albedo.png"])
        self.assertTrue(preflight["bundle"]["supportedForPackaging"])
        self.assertEqual(preflight["warnings"], [])

    def test_final_model_preflight_blocks_unsupported_format(self):
        root = database.PROCESSED_DIR / self.project_id / "target_models"
        root.mkdir(parents=True, exist_ok=True)
        path = root / "final.ply"
        path.write_bytes(b"ply")
        model_artifact_repository.add_artifact(
            self.project_id, "mesh", "manual", path.name, path.stat().st_size, str(path), str(path.relative_to(database.PROCESSED_DIR)),
            "Unsupported target", None, {}, model_format="ply", primary_file_path=str(path), status="ready",
            metadata={"artifactRole": "target_model"},
        )
        preflight = self.client.get(f"/projects/{self.project_id}/final-model/preflight").json()
        self.assertEqual(preflight["status"], "blocked")
        self.assertEqual(preflight["finalModel"]["format"], "unsupported")
        self.assertFalse(preflight["packageReady"])

    def test_final_model_preflight_warns_for_large_file_and_reports_promoted_source(self):
        source = self.generated_artifact(content=b"glTF\x02\x00\x00\x00")
        self.client.post(f"/projects/{self.project_id}/target-model/promote", json={"artifactId": source["artifactId"]})
        with patch.dict("os.environ", {"STRUCTURA_FINAL_MODEL_LARGE_MB": "0"}):
            preflight = self.client.get(f"/projects/{self.project_id}/final-model/preflight").json()
        self.assertEqual(preflight["status"], "warning")
        self.assertEqual(preflight["finalModel"]["source"], "promoted")
        self.assertTrue(any("large" in warning for warning in preflight["warnings"]))

    def test_delivery_manifest_requires_final_model_and_includes_virtual_metadata(self):
        manifest = self.client.get(f"/projects/{self.project_id}/delivery-manifest").json()
        self.assertFalse(manifest["ready"])
        self.assertIn("final_model", manifest["missingRequired"])
        self.assertEqual(next(item for item in manifest["items"] if item["kind"] == "metadata")["ready"], True)
        self.assertEqual(manifest["packageVersion"], "1.0")
        self.assertFalse(manifest["downloadable"])
        self.assertIsNone(manifest["downloadUrl"])
        self.assertIn("final_model", manifest["metadataPreview"]["missingRequired"])
        self.assertEqual(manifest["finalModelQuality"]["status"], "missing")
        self.assertFalse(manifest["finalModelQuality"]["packageReady"])
        self.assertIsNone(manifest["finalModelQuality"]["format"])
        self.assertIsNone(manifest["finalModelQuality"]["thumbnail"])

    def test_delivery_manifest_is_ready_with_target_and_resets_after_delete(self):
        uploaded = self.upload("final.obj", b"v 0 0 0\n").json()
        manifest = self.client.get(f"/projects/{self.project_id}/delivery-manifest").json()
        final_item = next(item for item in manifest["items"] if item["kind"] == "final_model")
        self.assertTrue(manifest["ready"])
        self.assertTrue(final_item["ready"])
        self.assertEqual(final_item["filename"], uploaded["filename"])
        self.assertEqual(manifest["packageFilename"], f"structura-project-{self.project_id}-delivery.zip")
        self.assertFalse(manifest["downloadable"])
        self.assertIsNone(manifest["downloadUrl"])
        self.assertIsNone(manifest["latestPackage"])
        self.assertEqual(manifest["metadataPreview"]["finalModel"]["filename"], uploaded["filename"])
        self.assertEqual(manifest["finalModelQuality"]["status"], "warning")
        self.assertTrue(manifest["finalModelQuality"]["packageReady"])
        self.assertEqual(manifest["finalModelQuality"]["format"], "obj")
        self.assertTrue(manifest["finalModelQuality"]["warnings"])
        self.assertEqual(manifest["finalModelQuality"]["bundle"], {"hasMtl": False, "hasTextures": False, "mtlFileCount": 0, "textureFileCount": 0, "supportedForPackaging": True})
        self.client.delete(f"/projects/{self.project_id}/target-model")
        self.assertFalse(self.client.get(f"/projects/{self.project_id}/delivery-manifest").json()["ready"])

    def test_delivery_manifest_includes_ready_glb_quality_summary(self):
        uploaded = self.upload("final.glb", b"glTF\x02\x00\x00\x00").json()
        quality = self.client.get(f"/projects/{self.project_id}/delivery-manifest").json()["finalModelQuality"]
        self.assertEqual(quality["status"], "ready")
        self.assertTrue(quality["packageReady"])
        self.assertEqual(quality["format"], "glb")
        self.assertEqual(quality["sizeBytes"], uploaded["sizeBytes"])
        self.assertEqual(quality["source"], "uploaded")
        self.assertEqual(quality["warnings"], [])
        self.assertEqual(quality["blockers"], [])
        self.assertIsNone(quality["bundle"])
        self.assertIsNone(quality["thumbnail"])

    def test_delivery_manifest_includes_compact_thumbnail_summary(self):
        uploaded = self.upload("final.glb", b"glTF\x02\x00\x00\x00").json()
        model_path = Path(uploaded["primary_file_path"])
        model_path.with_name(f"{model_path.stem}.thumbnail.png").write_bytes(b"png")
        thumbnail = self.client.get(f"/projects/{self.project_id}/delivery-manifest").json()["finalModelQuality"]["thumbnail"]
        self.assertEqual(thumbnail, {"available": True, "format": "png", "sizeBytes": 3, "source": "final_model_sidecar", "supportedForPackaging": True})
        self.assertNotIn("filename", thumbnail)
        self.assertNotIn("fileUrl", thumbnail)

    def test_delivery_manifest_includes_obj_mtl_bundle_summary(self):
        uploaded = self.upload("final.obj", b"v 0 0 0\n").json()
        (Path(uploaded["primary_file_path"]).parent / "final.mtl").write_text("newmtl material\n")
        bundle = self.client.get(f"/projects/{self.project_id}/delivery-manifest").json()["finalModelQuality"]["bundle"]
        self.assertTrue(bundle["hasMtl"])
        self.assertFalse(bundle["hasTextures"])
        self.assertEqual(bundle["mtlFileCount"], 1)
        self.assertEqual(bundle["textureFileCount"], 0)
        self.assertTrue(bundle["supportedForPackaging"])

    def test_delivery_manifest_includes_obj_texture_bundle_summary(self):
        uploaded = self.upload("final.obj", b"v 0 0 0\n").json()
        (Path(uploaded["primary_file_path"]).parent / "albedo.png").write_bytes(b"png")
        bundle = self.client.get(f"/projects/{self.project_id}/delivery-manifest").json()["finalModelQuality"]["bundle"]
        self.assertFalse(bundle["hasMtl"])
        self.assertTrue(bundle["hasTextures"])
        self.assertEqual(bundle["mtlFileCount"], 0)
        self.assertEqual(bundle["textureFileCount"], 1)
        self.assertTrue(bundle["supportedForPackaging"])

    def test_delivery_manifest_includes_blocked_unsupported_quality_summary(self):
        root = database.PROCESSED_DIR / self.project_id / "target_models"
        root.mkdir(parents=True, exist_ok=True)
        path = root / "final.ply"
        path.write_bytes(b"ply")
        model_artifact_repository.add_artifact(
            self.project_id, "mesh", "manual", path.name, path.stat().st_size, str(path), str(path.relative_to(database.PROCESSED_DIR)),
            "Unsupported target", None, {}, model_format="ply", primary_file_path=str(path), status="ready",
            metadata={"artifactRole": "target_model"},
        )
        quality = self.client.get(f"/projects/{self.project_id}/delivery-manifest").json()["finalModelQuality"]
        self.assertEqual(quality["status"], "blocked")
        self.assertFalse(quality["packageReady"])
        self.assertEqual(quality["format"], "unsupported")
        self.assertTrue(quality["blockers"])

    def test_delivery_zip_contains_model_and_metadata(self):
        self.assertEqual(self.client.get(f"/projects/{self.project_id}/delivery-package.zip").status_code, 404)
        self.upload("final.glb", b"glTF\x02\x00\x00\x00")
        response = self.download_latest_delivery_package()
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(BytesIO(response.content)) as package:
            self.assertIn("final_model.glb", package.namelist())
            metadata = json.loads(package.read("delivery-metadata.json"))
        self.assertEqual(metadata["projectId"], self.project_id)
        self.assertEqual(metadata["packageVersion"], "1.0")
        self.assertIn("generatedAt", metadata)
        self.assertIn("finalModel", metadata)
        self.assertIn("manifest", metadata)
        self.assertIsNone(metadata["objBundle"])
        self.assertEqual(metadata["previewImage"], {"included": False})

    def test_obj_delivery_zip_includes_companions_and_bundle_metadata(self):
        uploaded = self.upload("final.obj", b"mtllib final.mtl\nv 0 0 0\n").json()
        model_path = Path(uploaded["primary_file_path"])
        (model_path.parent / "final.mtl").write_text("newmtl material\nmap_Kd albedo.png\n")
        (model_path.parent / "albedo.png").write_bytes(b"png")
        response = self.download_latest_delivery_package()
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(BytesIO(response.content)) as package:
            self.assertEqual(set(package.namelist()), {"final_model.obj", "final.mtl", "albedo.png", "delivery-metadata.json"})
            metadata = json.loads(package.read("delivery-metadata.json"))
        self.assertEqual(metadata["objBundle"], {"included": True, "mtlFiles": ["final.mtl"], "textureFiles": ["albedo.png"], "supportedForPackaging": True})
        self.assertEqual(metadata["previewImage"], {"included": False})

    def test_standalone_obj_delivery_zip_remains_valid(self):
        self.upload("final.obj", b"v 0 0 0\n")
        response = self.download_latest_delivery_package()
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(BytesIO(response.content)) as package:
            self.assertEqual(set(package.namelist()), {"final_model.obj", "delivery-metadata.json"})
            metadata = json.loads(package.read("delivery-metadata.json"))
        self.assertEqual(metadata["objBundle"], {"included": False, "mtlFiles": [], "textureFiles": [], "supportedForPackaging": True})
        self.assertEqual(metadata["previewImage"], {"included": False})

    def test_glb_delivery_zip_includes_png_thumbnail_and_metadata(self):
        uploaded = self.upload("final.glb", b"glTF\x02\x00\x00\x00").json()
        model_path = Path(uploaded["primary_file_path"])
        model_path.with_name(f"{model_path.stem}.thumbnail.png").write_bytes(b"png")
        response = self.download_latest_delivery_package()
        with zipfile.ZipFile(BytesIO(response.content)) as package:
            self.assertEqual(set(package.namelist()), {"final_model.glb", "final_model_preview.png", "delivery-metadata.json"})
            metadata = json.loads(package.read("delivery-metadata.json"))
        self.assertEqual(metadata["previewImage"], {"included": True, "filename": "final_model_preview.png", "source": "final_model_sidecar", "format": "png", "sizeBytes": 3})

    def test_obj_delivery_zip_includes_companions_and_jpg_thumbnail(self):
        uploaded = self.upload("final.obj", b"v 0 0 0\n").json()
        model_path = Path(uploaded["primary_file_path"])
        (model_path.parent / "final.mtl").write_text("newmtl material\n")
        (model_path.parent / "albedo.png").write_bytes(b"png")
        model_path.with_name(f"{model_path.stem}.thumbnail.jpg").write_bytes(b"jpg")
        response = self.download_latest_delivery_package()
        with zipfile.ZipFile(BytesIO(response.content)) as package:
            self.assertEqual(set(package.namelist()), {"final_model.obj", "final.mtl", "albedo.png", "final_model_preview.jpg", "delivery-metadata.json"})
            metadata = json.loads(package.read("delivery-metadata.json"))
        self.assertEqual(metadata["previewImage"]["format"], "jpg")
        self.assertEqual(metadata["previewImage"]["filename"], "final_model_preview.jpg")

    def test_delivery_zip_prevents_thumbnail_archive_name_collision(self):
        uploaded = self.upload("final.obj", b"v 0 0 0\n").json()
        model_path = Path(uploaded["primary_file_path"])
        (model_path.parent / "final_model_preview.png").write_bytes(b"texture")
        model_path.with_name(f"{model_path.stem}.thumbnail.png").write_bytes(b"thumbnail")
        response = self.download_latest_delivery_package()
        with zipfile.ZipFile(BytesIO(response.content)) as package:
            names = package.namelist()
            self.assertEqual(names.count("final_model_preview.png"), 1)
            self.assertEqual(package.read("final_model_preview.png"), b"thumbnail")


if __name__ == "__main__":
    unittest.main()
