import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.repositories import realityscan_job_repository
from app.services import realityscan_service
from app.services.realityscan_service import parse_progress_file


class RealityScanProgressTests(unittest.TestCase):
    def test_validated_images_rejects_an_active_capture_job(self):
        with patch.object(realityscan_service.job_progress_service, "get", return_value={"status": "running"}):
            with self.assertRaisesRegex(ValueError, "Waiting for capture processing to finish"):
                realityscan_service._validated_images("project")

    def test_validated_images_requires_completed_capture_metadata(self):
        with patch.object(realityscan_service.job_progress_service, "get", return_value={"status": "completed"}), \
             patch.object(realityscan_service.capture_repository, "get_capture_metadata", return_value=None):
            with self.assertRaisesRegex(ValueError, "Waiting for validated images"):
                realityscan_service._validated_images("project")

    def test_validated_images_requires_twenty_processed_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frames = root / "project" / "frames"
            frames.mkdir(parents=True)
            for index in range(19):
                (frames / f"frame_{index:04d}.jpg").touch()
            with patch.object(realityscan_service.job_progress_service, "get", return_value={"status": "completed"}), \
                 patch.object(realityscan_service.capture_repository, "get_capture_metadata", return_value={"extracted_frame_count": 19}), \
                 patch.object(realityscan_service, "PROCESSED_DIR", root):
                with self.assertRaisesRegex(ValueError, "At least 20 validated images are required"):
                    realityscan_service._validated_images("project")

    def test_validated_images_accepts_completed_capture_with_twenty_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frames = root / "project" / "frames"
            frames.mkdir(parents=True)
            for index in range(20):
                (frames / f"frame_{index:04d}.jpg").touch()
            with patch.object(realityscan_service.job_progress_service, "get", return_value={"status": "completed"}), \
                 patch.object(realityscan_service.capture_repository, "get_capture_metadata", return_value={"extracted_frame_count": 20}), \
                 patch.object(realityscan_service, "PROCESSED_DIR", root):
                self.assertEqual(len(realityscan_service._validated_images("project")), 20)

    def test_algorithm_local_progress_is_mapped_to_stage_weighted_progress(self):
        # 20561 is mesh reconstruction; a later texture/export task starts at
        # zero. Raw values are intentionally not compared as one global value.
        with tempfile.TemporaryDirectory() as directory:
            progress_file = Path(directory) / "progress.txt"
            progress_file.write_text("20561 0.50 20.0 90.0 #progress\n20533 0.09 0.5 12.0 #progress\n")
            event = parse_progress_file(progress_file)

        self.assertEqual(event["alg_id"], "20533")
        self.assertEqual(event["stage_key"], "texturing")
        self.assertAlmostEqual(event["raw_progress"], 0.09)
        self.assertGreater(event["progress"], 0.78)

    def test_repository_never_persists_lower_overall_progress(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute("""CREATE TABLE realityscan_jobs (
            id TEXT PRIMARY KEY, progress REAL, eta_seconds REAL,
            elapsed_seconds REAL, stage TEXT, raw_progress REAL,
            raw_eta_seconds REAL, raw_elapsed_seconds REAL, raw_alg_id TEXT,
            updated_at TEXT)""")
        connection.execute("INSERT INTO realityscan_jobs (id, progress) VALUES ('job', 0.50)")

        # The persisted aggregate is protected even if a malformed or unknown
        # future task would calculate a lower overall estimate.
        with patch.object(realityscan_job_repository, "get_connection", return_value=connection):
            realityscan_job_repository.update_job_progress("job", 0.09, stage="launching_realityscan")

        self.assertEqual(connection.execute("SELECT progress FROM realityscan_jobs WHERE id = 'job'").fetchone()[0], 0.50)


if __name__ == "__main__":
    unittest.main()
