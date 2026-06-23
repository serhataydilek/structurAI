import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import database, main


class CompareAlignmentApiTests(unittest.TestCase):
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
        self.client_context = TestClient(main.app)
        self.client = self.client_context.__enter__()
        self.project_id = self.create_project("Alignment test")

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

    def url(self, project_id: str | None = None) -> str:
        return f"/projects/{project_id or self.project_id}/compare-alignment"

    def payload(self, **changes):
        return {"positionX": 1.5, "positionY": -2, "positionZ": 0.4, "rotationYDegrees": 45, "scale": 1.25, **changes}

    def test_get_returns_default_when_absent(self):
        self.assertEqual(self.client.get(self.url()).json(), {"positionX": 0.0, "positionY": 0.0, "positionZ": 0.0, "rotationYDegrees": 0.0, "scale": 1.0})

    def test_put_saves_and_get_returns_alignment(self):
        response = self.client.put(self.url(), json=self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["positionX"], 1.5)
        self.assertIn("updatedAt", response.json())
        self.assertEqual(self.client.get(self.url()).json()["rotationYDegrees"], 45.0)

    def test_put_rejects_out_of_range_values(self):
        for payload in (self.payload(positionX=10.1), self.payload(rotationYDegrees=181), self.payload(scale=5.1)):
            self.assertEqual(self.client.put(self.url(), json=payload).status_code, 422)

    def test_delete_returns_defaults(self):
        self.client.put(self.url(), json=self.payload())
        self.assertEqual(self.client.delete(self.url()).json(), {"positionX": 0.0, "positionY": 0.0, "positionZ": 0.0, "rotationYDegrees": 0.0, "scale": 1.0})
        self.assertEqual(self.client.get(self.url()).json()["scale"], 1.0)

    def test_alignment_is_project_scoped(self):
        other_id = self.create_project("Other project")
        self.client.put(self.url(), json=self.payload(positionX=3))
        self.assertEqual(self.client.get(self.url(other_id)).json()["positionX"], 0.0)


if __name__ == "__main__":
    unittest.main()
