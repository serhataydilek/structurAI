import json
import hashlib
import tempfile
import time
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import database, main
from app.repositories import delivery_package_repository
from app.services import delivery_package_service, model_artifact_service, report_artifact_service


class DeliveryPackageServiceTests(unittest.TestCase):
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
        self.project_id = self.client.post("/projects", json={"name": "Delivery package service", "siteType": "Office", "description": ""}).json()["id"]

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        for _ in range(10):
            try:
                self.temp.cleanup()
                break
            except PermissionError:
                time.sleep(0.05)

    def upload(self, name: str, content: bytes) -> dict:
        return self.client.post(f"/projects/{self.project_id}/target-model", files={"file": (name, content)}).json()

    def generate(self) -> dict:
        return delivery_package_service.generate_persisted_package(
            self.project_id,
            self.client.get(f"/projects/{self.project_id}/delivery-manifest").json(),
        )

    def test_generates_version_one_glb_snapshot_with_record_and_metadata(self):
        self.upload("final.glb", b"glTF\x02\x00\x00\x00")

        record = self.generate()
        path = Path(record["storagePath"])
        self.assertEqual(record["version"], 1)
        self.assertTrue(path.is_file())
        self.assertEqual(record["sizeBytes"], path.stat().st_size)
        self.assertEqual(delivery_package_repository.get_package(record["packageId"]), record)
        self.assertEqual(delivery_package_service.package_record_to_api(record), {
            "id": record["packageId"], "projectId": self.project_id, "version": 1,
            "filename": record["filename"], "sizeBytes": record["sizeBytes"], "createdAt": record["createdAt"],
            "downloadUrl": f"/projects/{self.project_id}/delivery-packages/{record['packageId']}/download",
            "reportArtifact": record["metadata"]["reportArtifact"],
        })
        with zipfile.ZipFile(path) as package:
            self.assertEqual(set(package.namelist()), {"final_model.glb", "report.md", "delivery-metadata.json"})
            metadata = json.loads(package.read("delivery-metadata.json"))
            report_content = package.read("report.md")
        self.assertEqual(metadata["package"], {"id": record["packageId"], "version": 1})
        self.assertEqual(metadata["reportArtifact"], {
            "filename": "report.md",
            "format": "md",
            "contentType": "text/markdown; charset=utf-8",
            "sizeBytes": len(report_content),
            "sha256": hashlib.sha256(report_content).hexdigest(),
        })
        self.assertEqual(record["metadata"], metadata)

    def test_generates_obj_bundle_preview_snapshot(self):
        uploaded = self.upload("final.obj", b"v 0 0 0\n")
        model_path = Path(uploaded["primary_file_path"])
        (model_path.parent / "final.mtl").write_text("newmtl material\n")
        (model_path.parent / "albedo.png").write_bytes(b"png")
        model_path.with_name(f"{model_path.stem}.thumbnail.jpg").write_bytes(b"jpg")

        record = self.generate()

        with zipfile.ZipFile(record["storagePath"]) as package:
            self.assertEqual(set(package.namelist()), {"final_model.obj", "final.mtl", "albedo.png", "final_model_preview.jpg", "report.md", "delivery-metadata.json"})
            metadata = json.loads(package.read("delivery-metadata.json"))
        self.assertEqual(metadata["previewImage"]["filename"], "final_model_preview.jpg")
        self.assertEqual(metadata["objBundle"]["textureFiles"], ["albedo.png"])
        self.assertEqual(metadata["reportArtifact"]["filename"], "report.md")

    def test_consecutive_generations_create_version_history(self):
        self.upload("final.glb", b"glTF\x02\x00\x00\x00")

        first = self.generate()
        second = self.generate()

        self.assertEqual((first["version"], second["version"]), (1, 2))
        self.assertEqual([item["packageId"] for item in delivery_package_repository.list_packages(self.project_id)], [second["packageId"], first["packageId"]])
        self.assertEqual(delivery_package_repository.get_latest_package(self.project_id), second)

    def test_not_ready_generation_does_not_create_record_or_package_directory(self):
        manifest = self.client.get(f"/projects/{self.project_id}/delivery-manifest").json()

        with self.assertRaises(delivery_package_service.DeliveryPackageError) as context:
            delivery_package_service.generate_persisted_package(self.project_id, manifest)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(delivery_package_repository.list_packages(self.project_id), [])
        self.assertFalse((database.PROCESSED_DIR / self.project_id / "delivery_packages").exists())

    def test_report_rendering_failure_does_not_persist_package_or_file(self):
        self.upload("final.glb", b"glTF\x02\x00\x00\x00")
        manifest = self.client.get(f"/projects/{self.project_id}/delivery-manifest").json()

        with patch.object(report_artifact_service, "build_report_markdown", side_effect=RuntimeError("render failed")):
            with self.assertRaisesRegex(RuntimeError, "render failed"):
                delivery_package_service.generate_persisted_package(self.project_id, manifest)

        self.assertEqual(delivery_package_repository.list_packages(self.project_id), [])
        self.assertFalse((database.PROCESSED_DIR / self.project_id / "delivery_packages").exists())

    def test_legacy_get_delivery_zip_requires_a_persisted_package(self):
        self.upload("final.glb", b"glTF\x02\x00\x00\x00")

        response = self.client.get(f"/projects/{self.project_id}/delivery-package.zip")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(delivery_package_repository.list_packages(self.project_id), [])


if __name__ == "__main__":
    unittest.main()
