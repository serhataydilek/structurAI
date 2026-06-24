import json
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
from app.services import model_artifact_service


class DeliveryPackageApiTests(unittest.TestCase):
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
        self.project_id = self.create_project("Delivery package API")

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

    def create_project(self, name: str) -> str:
        return self.client.post("/projects", json={"name": name, "siteType": "Office", "description": ""}).json()["id"]

    def upload(self, name: str, content: bytes) -> dict:
        return self.client.post(f"/projects/{self.project_id}/target-model", files={"file": (name, content)}).json()

    def generate(self) -> dict:
        response = self.client.post(f"/projects/{self.project_id}/delivery-packages")
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_post_creates_version_one_and_second_post_creates_version_two(self):
        self.upload("final.glb", b"glTF\x02\x00\x00\x00")

        first = self.generate()
        second = self.generate()

        self.assertEqual((first["version"], second["version"]), (1, 2))
        self.assertTrue(Path(delivery_package_repository.get_package(first["id"])["storagePath"]).is_file())
        listed = self.client.get(f"/projects/{self.project_id}/delivery-packages")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item["id"] for item in listed.json()], [second["id"], first["id"]])

    def test_download_returns_exact_persisted_zip_without_rebuilding(self):
        uploaded = self.upload("final.glb", b"glTF\x02\x00\x00\x00")
        model_path = Path(uploaded["primary_file_path"])
        thumbnail = model_path.with_name(f"{model_path.stem}.thumbnail.png")
        thumbnail.write_bytes(b"original-preview")
        package = self.generate()
        record = delivery_package_repository.get_package(package["id"])
        persisted_bytes = Path(record["storagePath"]).read_bytes()
        thumbnail.write_bytes(b"changed-preview")

        response = self.client.get(package["downloadUrl"])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, persisted_bytes)
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            self.assertEqual(archive.read("final_model_preview.png"), b"original-preview")
            self.assertEqual(json.loads(archive.read("delivery-metadata.json"))["package"]["version"], 1)

    def test_unknown_and_cross_project_package_downloads_return_not_found(self):
        self.upload("final.glb", b"glTF\x02\x00\x00\x00")
        package = self.generate()
        other_project_id = self.create_project("Other project")

        self.assertEqual(self.client.get(f"/projects/{self.project_id}/delivery-packages/not-a-package/download").status_code, 404)
        self.assertEqual(self.client.get(f"/projects/{other_project_id}/delivery-packages/{package['id']}/download").status_code, 404)

    def test_not_ready_post_creates_no_record_or_package_directory(self):
        response = self.client.post(f"/projects/{self.project_id}/delivery-packages")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(delivery_package_repository.list_packages(self.project_id), [])
        self.assertFalse((database.PROCESSED_DIR / self.project_id / "delivery_packages").exists())

    def test_manifest_exposes_latest_package_and_legacy_route_downloads_it(self):
        uploaded = self.upload("final.glb", b"glTF\x02\x00\x00\x00")
        model_path = Path(uploaded["primary_file_path"])
        thumbnail = model_path.with_name(f"{model_path.stem}.thumbnail.png")
        thumbnail.write_bytes(b"original-preview")

        before = self.client.get(f"/projects/{self.project_id}/delivery-manifest").json()
        self.assertIsNone(before["latestPackage"])
        self.assertFalse(before["downloadable"])
        self.assertIsNone(before["downloadUrl"])
        self.assertEqual(before["packageVersion"], "1.0")
        self.assertEqual(before["packageFormatVersion"], "1.0")

        first = self.generate()
        self.assertEqual(first["reportArtifact"]["filename"], "report.md")
        self.assertEqual(first["reportArtifact"]["format"], "md")
        first_record = delivery_package_repository.get_package(first["id"])
        first_bytes = Path(first_record["storagePath"]).read_bytes()
        thumbnail.write_bytes(b"changed-preview")

        response = self.client.get(f"/projects/{self.project_id}/delivery-package.zip")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, first_bytes)
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            self.assertEqual(archive.read("final_model_preview.png"), b"original-preview")
        manifest = self.client.get(f"/projects/{self.project_id}/delivery-manifest").json()
        self.assertTrue(manifest["downloadable"])
        self.assertEqual(manifest["downloadUrl"], first["downloadUrl"])
        self.assertEqual(manifest["latestPackage"], first)
        self.assertEqual(manifest["latestPackage"]["reportArtifact"], first_record["metadata"]["reportArtifact"])

        second = self.generate()
        latest_manifest = self.client.get(f"/projects/{self.project_id}/delivery-manifest").json()
        self.assertEqual(latest_manifest["latestPackage"], second)
        self.assertEqual(latest_manifest["downloadUrl"], second["downloadUrl"])

    def test_manifest_omits_report_artifact_for_legacy_package_metadata(self):
        record = delivery_package_repository.create_package(
            self.project_id,
            1,
            "legacy.zip",
            "C:/legacy.zip",
            "legacy.zip",
            1,
            {"package": {"id": "legacy", "version": 1}},
            package_id="legacy",
        )

        manifest = self.client.get(f"/projects/{self.project_id}/delivery-manifest").json()

        self.assertEqual(manifest["latestPackage"]["id"], record["packageId"])
        self.assertNotIn("reportArtifact", manifest["latestPackage"])

    def test_legacy_route_returns_not_found_before_package_generation(self):
        self.upload("final.glb", b"glTF\x02\x00\x00\x00")

        response = self.client.get(f"/projects/{self.project_id}/delivery-package.zip")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(delivery_package_repository.list_packages(self.project_id), [])


if __name__ == "__main__":
    unittest.main()
