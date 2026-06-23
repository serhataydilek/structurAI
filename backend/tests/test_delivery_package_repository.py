import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import database
from app.repositories import delivery_package_repository, project_repository


class DeliveryPackageRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [
            patch.object(database, "STORAGE_DIR", root),
            patch.object(database, "UPLOADS_DIR", root / "uploads"),
            patch.object(database, "PROCESSED_DIR", root / "processed"),
            patch.object(database, "DB_PATH", root / "structura.db"),
        ]
        for item in self.patches:
            item.start()
        database.init_db()
        self.project_one = project_repository.create_project("Package one", "Office", "")["id"]
        self.project_two = project_repository.create_project("Package two", "Office", "")["id"]

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        for _ in range(10):
            try:
                self.temp.cleanup()
                break
            except PermissionError:
                time.sleep(0.05)

    def create_package(self, project_id: str, version: int):
        return delivery_package_repository.create_package(
            project_id,
            version,
            f"delivery-v{version}.zip",
            f"C:/packages/{project_id}/delivery-v{version}.zip",
            f"{project_id}/delivery_packages/delivery-v{version}.zip",
            version * 100,
            {"package": {"version": version}},
        )

    def test_creates_and_gets_package_record(self):
        created = self.create_package(self.project_one, 1)

        self.assertEqual(created["projectId"], self.project_one)
        self.assertEqual(created["version"], 1)
        self.assertEqual(created["metadata"], {"package": {"version": 1}})
        self.assertEqual(delivery_package_repository.get_package(created["packageId"]), created)
        self.assertEqual(delivery_package_repository.get_package_for_project(self.project_one, created["packageId"]), created)

    def test_lists_and_gets_latest_package_newest_version_first(self):
        first = self.create_package(self.project_one, 1)
        second = self.create_package(self.project_one, 2)

        self.assertEqual([item["packageId"] for item in delivery_package_repository.list_packages(self.project_one)], [second["packageId"], first["packageId"]])
        self.assertEqual(delivery_package_repository.get_latest_package(self.project_one), second)

    def test_next_version_starts_at_one_and_is_scoped_by_project(self):
        self.assertEqual(delivery_package_repository.get_next_version(self.project_one), 1)
        self.create_package(self.project_one, 1)
        self.assertEqual(delivery_package_repository.get_next_version(self.project_one), 2)
        self.assertEqual(delivery_package_repository.get_next_version(self.project_two), 1)

    def test_duplicate_version_for_project_is_rejected(self):
        self.create_package(self.project_one, 1)

        with self.assertRaises(sqlite3.IntegrityError):
            self.create_package(self.project_one, 1)

        self.create_package(self.project_two, 1)

    def test_project_scoped_lookup_rejects_cross_project_package(self):
        package = self.create_package(self.project_one, 1)

        self.assertIsNone(delivery_package_repository.get_package_for_project(self.project_two, package["packageId"]))


if __name__ == "__main__":
    unittest.main()
