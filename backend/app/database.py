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
            """
        )
        _ensure_column(conn, "capture_metadata", "selected_fps_mode", "TEXT NOT NULL DEFAULT 'Balanced'")
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


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
