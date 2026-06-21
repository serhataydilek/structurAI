from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
PROCESSED_DIR = STORAGE_DIR / "processed"
DB_PATH = STORAGE_DIR / "structura.db"


def get_connection() -> sqlite3.Connection:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                site_type TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                scan_type TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                processing_started_at TEXT
            );

            CREATE TABLE IF NOT EXISTS media (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                media_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS annotations (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS capture_metadata (
                project_id TEXT PRIMARY KEY,
                uploaded_media_count INTEGER NOT NULL,
                extracted_frame_count INTEGER NOT NULL,
                image_count INTEGER NOT NULL,
                video_count INTEGER NOT NULL,
                selected_fps_mode TEXT NOT NULL DEFAULT 'Balanced',
                extraction_fps INTEGER NOT NULL DEFAULT 2,
                average_sharpness REAL,
                blurry_frame_count INTEGER NOT NULL DEFAULT 0,
                blurry_frame_percentage REAL NOT NULL DEFAULT 0,
                sharpness_available INTEGER NOT NULL DEFAULT 1,
                workspace_path TEXT NOT NULL,
                extraction_method TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                next_step TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reconstruction_metadata (
                project_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                colmap_available INTEGER NOT NULL,
                colmap_version TEXT,
                input_frame_count INTEGER NOT NULL,
                selected_fps_mode TEXT NOT NULL DEFAULT 'Balanced',
                extraction_fps INTEGER NOT NULL DEFAULT 2,
                matching_mode TEXT NOT NULL DEFAULT 'Photo Exhaustive',
                sparse_output_exists INTEGER NOT NULL,
                dense_status TEXT NOT NULL DEFAULT 'Dense Reconstruction Not Started',
                dense_output_exists INTEGER NOT NULL DEFAULT 0,
                dense_point_count INTEGER NOT NULL DEFAULT 0,
                dense_output_path TEXT,
                dense_log_files_json TEXT NOT NULL DEFAULT '[]',
                dense_warnings_json TEXT NOT NULL DEFAULT '[]',
                dense_error_message TEXT,
                sparse_model_folders_json TEXT NOT NULL,
                log_files_json TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                error_message TEXT,
                started_at TEXT,
                completed_at TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reconstruction_attempts (
                attempt_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                extracted_frame_count INTEGER NOT NULL,
                source_frame_count INTEGER NOT NULL DEFAULT 0,
                selected_frame_count INTEGER NOT NULL DEFAULT 0,
                frame_selection_mode TEXT NOT NULL DEFAULT 'All frames',
                selected_frame_folder TEXT,
                registered_image_count INTEGER NOT NULL DEFAULT 0,
                registration_ratio REAL NOT NULL DEFAULT 0,
                sparse_point_count INTEGER NOT NULL DEFAULT 0,
                sparse_quality_label TEXT NOT NULL DEFAULT 'Poor Sparse Reconstruction',
                matching_mode TEXT NOT NULL DEFAULT 'Photo Exhaustive',
                selected_fps TEXT NOT NULL DEFAULT 'Balanced',
                extraction_fps INTEGER NOT NULL DEFAULT 2,
                status TEXT NOT NULL,
                output_path TEXT,
                log_files_json TEXT NOT NULL DEFAULT '[]',
                sparse_model_folders_json TEXT NOT NULL DEFAULT '[]',
                scene_analysis_summary_json TEXT NOT NULL DEFAULT '{}',
                viewer_transform_json TEXT NOT NULL DEFAULT '{}',
                viewer_preview_mode TEXT NOT NULL DEFAULT 'auto',
                is_best_attempt INTEGER NOT NULL DEFAULT 0,
                failure_reason TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reconstruction_frame_selections (
                selection_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                source_frame_count INTEGER NOT NULL,
                selected_frame_count INTEGER NOT NULL,
                average_selected_sharpness REAL,
                selected_frame_filenames_json TEXT NOT NULL DEFAULT '[]',
                selected_frame_folder TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS report_cache (
                project_id TEXT PRIMARY KEY,
                cache_key TEXT NOT NULL,
                report_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS visual_preview_outputs (
                visual_preview_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                attempt_id TEXT NOT NULL,
                status TEXT NOT NULL,
                preview_type TEXT NOT NULL,
                source_attempt_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                output_path TEXT,
                manifest_path TEXT,
                training_status TEXT NOT NULL DEFAULT 'not_started',
                export_status TEXT NOT NULL DEFAULT 'not_started',
                training_started_at TEXT,
                training_finished_at TEXT,
                training_log_path TEXT,
                export_log_path TEXT,
                nerfstudio_config_path TEXT,
                splat_output_path TEXT,
                splat_output_size_bytes INTEGER,
                viewer_asset_path TEXT,
                error_message TEXT,
                summary_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS model_artifacts (
                artifact_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                source_tool TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                storage_path TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                role TEXT,
                stats_json TEXT NOT NULL DEFAULT '{}',
                bundle_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS artifact_comparisons (
                comparison_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                reference_artifact_id TEXT NOT NULL,
                current_artifact_id TEXT NOT NULL,
                status TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (reference_artifact_id) REFERENCES model_artifacts(artifact_id),
                FOREIGN KEY (current_artifact_id) REFERENCES model_artifacts(artifact_id)
            );

            CREATE TABLE IF NOT EXISTS photogrammetry_jobs (
                job_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, engine TEXT NOT NULL, status TEXT NOT NULL,
                input_image_folder TEXT NOT NULL, output_folder TEXT NOT NULL, command_file_path TEXT,
                command_used TEXT, log_path TEXT, log_tail TEXT NOT NULL DEFAULT '', started_at TEXT,
                finished_at TEXT, duration_seconds REAL, produced_artifact_id TEXT, notes TEXT NOT NULL DEFAULT '',
                errors_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS realityscan_jobs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN (
                    'pending', 'preparing', 'running', 'importing',
                    'completed', 'failed', 'cancelled'
                )),
                progress REAL,
                eta_seconds REAL,
                elapsed_seconds REAL,
                stage TEXT,
                raw_progress REAL,
                raw_eta_seconds REAL,
                raw_elapsed_seconds REAL,
                raw_alg_id TEXT,
                updated_at TEXT,
                image_count INTEGER,
                job_dir TEXT NOT NULL,
                images_dir TEXT,
                export_dir TEXT,
                progress_file_path TEXT,
                project_file_path TEXT,
                exported_model_path TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_realityscan_jobs_project_created
            ON realityscan_jobs (project_id, created_at DESC);
            """
        )
        _ensure_column(conn, "capture_metadata", "selected_fps_mode", "TEXT NOT NULL DEFAULT 'Balanced'")
        _ensure_column(conn, "realityscan_jobs", "raw_progress", "REAL")
        _ensure_column(conn, "realityscan_jobs", "raw_eta_seconds", "REAL")
        _ensure_column(conn, "realityscan_jobs", "raw_elapsed_seconds", "REAL")
        _ensure_column(conn, "realityscan_jobs", "raw_alg_id", "TEXT")
        _ensure_column(conn, "realityscan_jobs", "updated_at", "TEXT")
        _ensure_column(conn, "capture_metadata", "extraction_fps", "INTEGER NOT NULL DEFAULT 2")
        _ensure_column(conn, "capture_metadata", "average_sharpness", "REAL")
        _ensure_column(conn, "capture_metadata", "blurry_frame_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "capture_metadata", "blurry_frame_percentage", "REAL NOT NULL DEFAULT 0")
        _ensure_column(conn, "capture_metadata", "sharpness_available", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(conn, "reconstruction_metadata", "selected_fps_mode", "TEXT NOT NULL DEFAULT 'Balanced'")
        _ensure_column(conn, "reconstruction_metadata", "extraction_fps", "INTEGER NOT NULL DEFAULT 2")
        _ensure_column(conn, "reconstruction_metadata", "matching_mode", "TEXT NOT NULL DEFAULT 'Photo Exhaustive'")
        _ensure_column(conn, "reconstruction_metadata", "dense_status", "TEXT NOT NULL DEFAULT 'Dense Reconstruction Not Started'")
        _ensure_column(conn, "reconstruction_metadata", "dense_output_exists", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "reconstruction_metadata", "dense_point_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "reconstruction_metadata", "dense_output_path", "TEXT")
        _ensure_column(conn, "reconstruction_metadata", "dense_log_files_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "reconstruction_metadata", "dense_warnings_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "reconstruction_metadata", "dense_error_message", "TEXT")
        _ensure_column(conn, "reconstruction_attempts", "source_frame_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "reconstruction_attempts", "selected_frame_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "reconstruction_attempts", "frame_selection_mode", "TEXT NOT NULL DEFAULT 'All frames'")
        _ensure_column(conn, "reconstruction_attempts", "selected_frame_folder", "TEXT")
        _ensure_column(conn, "reconstruction_attempts", "viewer_transform_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(conn, "reconstruction_attempts", "viewer_preview_mode", "TEXT NOT NULL DEFAULT 'auto'")
        _ensure_column(conn, "visual_preview_outputs", "training_status", "TEXT NOT NULL DEFAULT 'not_started'")
        _ensure_column(conn, "visual_preview_outputs", "export_status", "TEXT NOT NULL DEFAULT 'not_started'")
        _ensure_column(conn, "visual_preview_outputs", "training_started_at", "TEXT")
        _ensure_column(conn, "visual_preview_outputs", "training_finished_at", "TEXT")
        _ensure_column(conn, "visual_preview_outputs", "training_log_path", "TEXT")
        _ensure_column(conn, "visual_preview_outputs", "export_log_path", "TEXT")
        _ensure_column(conn, "visual_preview_outputs", "nerfstudio_config_path", "TEXT")
        _ensure_column(conn, "visual_preview_outputs", "splat_output_path", "TEXT")
        _ensure_column(conn, "visual_preview_outputs", "splat_output_size_bytes", "INTEGER")
        _ensure_column(conn, "visual_preview_outputs", "viewer_asset_path", "TEXT")
        _ensure_column(conn, "model_artifacts", "bundle_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(conn, "model_artifacts", "source_type", "TEXT")
        _ensure_column(conn, "model_artifacts", "job_id", "TEXT")
        _ensure_column(conn, "model_artifacts", "format", "TEXT")
        _ensure_column(conn, "model_artifacts", "primary_file_path", "TEXT")
        _ensure_column(conn, "model_artifacts", "mtl_file_path", "TEXT")
        _ensure_column(conn, "model_artifacts", "texture_dir_path", "TEXT")
        _ensure_column(conn, "model_artifacts", "status", "TEXT NOT NULL DEFAULT 'ready'")
        _ensure_column(conn, "model_artifacts", "metadata_json", "TEXT")
        _ensure_column(conn, "model_artifacts", "artifact_role", "TEXT NOT NULL DEFAULT 'raw_realityscan'")
        _ensure_column(conn, "model_artifacts", "source_artifact_id", "TEXT")
        _ensure_column(conn, "model_artifacts", "source_job_id", "TEXT")
        _ensure_column(conn, "artifact_comparisons", "analysis_status", "TEXT NOT NULL DEFAULT 'not_started'")
        _ensure_column(conn, "artifact_comparisons", "analysis_summary_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(conn, "artifact_comparisons", "warnings_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "artifact_comparisons", "reference_bounds_json", "TEXT")
        _ensure_column(conn, "artifact_comparisons", "current_bounds_json", "TEXT")
        _ensure_column(conn, "artifact_comparisons", "rough_bounds_delta_json", "TEXT")
        _ensure_column(conn, "artifact_comparisons", "scale_mismatch_warning", "TEXT")
        _ensure_column(conn, "artifact_comparisons", "no_progress_percentage_reason", "TEXT")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
