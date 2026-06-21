"""Isolated RealityScan CLI safety spike.

This script prepares a minimal RealityScan command-file job and prints the exact
command that would be executed. It is intentionally not wired into Structura's
API/product flow.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4


COMMON_REALITYSCAN_PATHS = [
    Path(r"C:\Program Files\Epic Games\RealityScan\RealityScan.exe"),
    Path(r"C:\Program Files\Epic Games\RealityScan_2.1\RealityScan.exe"),
]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def resolve_realityscan_exe() -> tuple[Path | None, str]:
    configured = os.getenv("REALITYSCAN_EXE")
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return path, "REALITYSCAN_EXE"
        return None, f"REALITYSCAN_EXE is set but does not point to a file: {path}"

    for path in COMMON_REALITYSCAN_PATHS:
        if path.is_file():
            return path, "common Windows install path"

    return None, "not found"


def quote_command_part(value: Path | str) -> str:
    text = str(value)
    return f'"{text}"' if any(char.isspace() for char in text) else text


def collect_images(input_folder: Path) -> list[Path]:
    if not input_folder.is_dir():
        raise ValueError(f"Input image folder does not exist: {input_folder}")
    images = sorted(path for path in input_folder.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    if not images:
        raise ValueError(f"No supported images found in {input_folder}. Supported: {', '.join(sorted(IMAGE_EXTENSIONS))}")
    return images


def write_export_params(path: Path) -> None:
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<ModelExport>
  <!-- Minimal OBJ export parameters for the isolated RealityScan CLI spike. -->
  <Format>obj</Format>
  <ExportTextures>true</ExportTextures>
  <ExportMaterials>true</ExportMaterials>
</ModelExport>
""",
        encoding="utf-8",
    )


def write_rscmd(path: Path, images_folder: Path, project_path: Path, model_path: Path, export_params_path: Path) -> None:
    commands = [
        "-newScene",
        f"-addFolder {quote_command_part(images_folder)}",
        "-align",
        "-selectMaximalComponent",
        "-setReconstructionRegionAuto",
        "-calculateNormalModel",
        "-unwrap",
        "-calculateTexture",
        f"-save {quote_command_part(project_path)}",
        f"-exportSelectedModel {quote_command_part(model_path)} {quote_command_part(export_params_path)}",
        "-quit",
    ]
    path.write_text("\n".join(commands) + "\n", encoding="utf-8")


def prepare_job(input_folder: Path, job_root: Path | None) -> dict[str, Path | list[Path]]:
    images = collect_images(input_folder)
    root = job_root or Path(tempfile.gettempdir()) / f"structura_realityscan_cli_spike_{uuid4().hex}"
    images_dir = root / "images"
    export_dir = root / "export"
    crash_dir = root / "crash"
    logs_dir = root / "logs"

    for folder in (images_dir, export_dir, crash_dir, logs_dir):
        folder.mkdir(parents=True, exist_ok=True)

    for image in images:
        shutil.copy2(image, images_dir / image.name)

    project_path = root / "project.rsproj"
    model_path = export_dir / "model.obj"
    export_params_path = root / "export_params.xml"
    command_file_path = root / "realityscan_job.rscmd"
    progress_path = logs_dir / "progress.txt"

    write_export_params(export_params_path)
    write_rscmd(command_file_path, images_dir, project_path, model_path, export_params_path)
    progress_path.write_text("RealityScan CLI spike prepared. Progress output is expected here when a real run is enabled.\n", encoding="utf-8")

    return {
        "root": root,
        "images_dir": images_dir,
        "export_dir": export_dir,
        "crash_dir": crash_dir,
        "logs_dir": logs_dir,
        "project_path": project_path,
        "model_path": model_path,
        "export_params_path": export_params_path,
        "command_file_path": command_file_path,
        "progress_path": progress_path,
        "images": images,
    }


def build_command(exe: Path, command_file_path: Path, logs_dir: Path) -> list[str]:
    return [str(exe), "-execRSCMD", str(command_file_path), "-stdConsole", "-writeProgress", str(logs_dir / "progress.txt")]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare and optionally run an isolated RealityScan CLI command-file spike.")
    parser.add_argument("input_image_folder", type=Path, help="Folder containing source images.")
    parser.add_argument("--job-root", type=Path, default=None, help="Optional output job folder. Defaults to a temporary folder.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Prepare files and print the command without running RealityScan. Default.")
    mode.add_argument("--run", action="store_true", help="Run the printed RealityScan command. Use only after verifying the generated .rscmd.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dry_run = not args.run
    input_folder = args.input_image_folder.expanduser().resolve()
    job_root = args.job_root.expanduser().resolve() if args.job_root else None

    exe, exe_source = resolve_realityscan_exe()
    if not exe:
        print(f"RealityScan executable: {exe_source}", file=sys.stderr)
        print("Set REALITYSCAN_EXE to RealityScan.exe before using --run.", file=sys.stderr)
        if args.run:
            return 2

    try:
        job = prepare_job(input_folder, job_root)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    command = build_command(exe or Path(r"C:\Path\To\RealityScan.exe"), job["command_file_path"], job["logs_dir"])  # type: ignore[arg-type]
    printable_command = " ".join(quote_command_part(part) for part in command)

    print(f"RealityScan executable source: {exe_source}")
    print(f"Job folder: {job['root']}")
    print(f"Copied images: {len(job['images'])}")
    print(f"Command file: {job['command_file_path']}")
    print(f"Export params: {job['export_params_path']}")
    print(f"Expected progress file: {job['progress_path']}")
    print(f"Expected project file: {job['project_path']}")
    print(f"Expected OBJ export: {job['model_path']}")
    print("RealityScan command:")
    print(printable_command)

    if dry_run:
        print("Dry run only. RealityScan was not launched.")
        return 0

    print("Running RealityScan command...")
    result = subprocess.run(command, cwd=str(job["root"]))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
