# Structura AI

## v0.4: External photogrammetry model workflow

Structura uses RealityScan as its primary client-quality model-generation path. Its active workflow is:

- Capture and optional sparse reconstruction validation.
- Generate the production mesh in RealityScan; use COLMAP only as optional capture/alignment validation.
- OBJ + MTL + texture ZIP or dense PLY import into Model Artifacts.
- Current/reference roles, measurement readiness, and future comparison.

Recommended immediate workflow: capture photos; validate capture in Structura; create a high-quality model in RealityCapture/Metashape/Pix4D; import it; mark the finished reference and current state; create a comparison record; then generate the report. Alignment and point-cloud distance analysis remain external (for example CloudCompare) until the internal comparison engine is implemented.

RealityScan model generation includes a stage-aware status card (alignment, component selection, mesh reconstruction, unwrap, texture, export, and import). Overall progress is persisted monotonically even though RealityScan's native progress file resets its percentage for each internal task. The UI updates elapsed time every second and shows `Estimating...` until an ETA is credible. Gaussian/Splatfacto remains an experimental visual-preview-only path.

v0.4 supports importing artifacts and creating comparison records. Real progress measurement requires externally generated dense point clouds or meshes; Gaussian Splat exports remain preview-only.

### RealityScan backend configuration

The backend diagnostics endpoint is `GET /photogrammetry/realityscan/diagnostics`. It only checks configuration and files; it never starts RealityScan.

- `REALITYSCAN_EXE`: optional full path to `RealityScan.exe`. When unset, Structura checks the standard Epic Games RealityScan installation paths.
- `REALITYSCAN_EXPORT_PARAMS`: optional full path to a RealityScan OBJ export parameters XML. When unset, Structura checks `config/realityscan_export_obj.xml`.
- `STRUCTURA_ENABLE_REALITYSCAN=true`: enables the RealityScan integration after its executable and export parameters are available.

Example PowerShell configuration:

```powershell
$env:REALITYSCAN_EXE = "C:\Program Files\Epic Games\RealityScan\RealityScan.exe"
$env:REALITYSCAN_EXPORT_PARAMS = "C:\path\to\realityscan_export_obj.xml"
$env:STRUCTURA_ENABLE_REALITYSCAN = "true"
```

Create the export-parameters XML in RealityScan rather than hand-writing it: export a model once through the **Export Model** dialog with **Export an info file** enabled, then copy the `<ModelExport>` element from the generated `.rsinfo` file into the XML referenced above. RealityScan rejects guessed or incomplete XML parameter files with `0x80070057` (`ERROR_INVALID_PARAMETER`).

For RealityScan, Metashape, and Pix4D textured exports, upload one ZIP that keeps the OBJ, MTL, and texture images together. High-poly exports can be very large; ZIP import manages the source artifact only and does not add a heavy browser viewer. Create a simplified or medium-resolution derivative later for web presentation.

## RealityScan CLI safety spike

`scripts/realityscan_cli_spike.py` is an isolated developer spike for preparing a RealityScan command-file job. It is not wired into the production API or main product flow yet.

Set the RealityScan executable explicitly when possible:

```powershell
$env:REALITYSCAN_EXE="C:\Program Files\Epic Games\RealityScan_2.1\RealityScan.exe"
```

If `REALITYSCAN_EXE` is not set, the spike checks these Windows install paths:

- `C:\Program Files\Epic Games\RealityScan\RealityScan.exe`
- `C:\Program Files\Epic Games\RealityScan_2.1\RealityScan.exe`

Dry-run mode is the default. It creates a temporary job folder, copies source images into `images/`, writes `realityscan_job.rscmd`, writes `export_params.xml`, and prints the exact command without launching RealityScan:

```powershell
python .\scripts\realityscan_cli_spike.py "C:\path\to\image-folder" --dry-run
```

To keep the generated files in a known folder:

```powershell
python .\scripts\realityscan_cli_spike.py "C:\path\to\image-folder" --job-root ".\files\realityscan-cli-spike" --dry-run
```

Run for real only after reviewing the generated `.rscmd` and confirming this RealityScan version supports `-execRSCMD`, `-stdConsole`, and `-writeProgress`:

```powershell
python .\scripts\realityscan_cli_spike.py "C:\path\to\image-folder" --job-root ".\files\realityscan-cli-spike" --run
```

Expected spike folder layout:

- `images/` — copied input images used by `-addFolder`
- `export/` — expected `model.obj` output location
- `crash/` — reserved for crash artifacts/manual collection
- `logs/progress.txt` — expected progress log path passed to RealityScan
- `project.rsproj` — expected saved RealityScan project
- `realityscan_job.rscmd` — generated command file
- `export_params.xml` — minimal OBJ export parameter file

The generated `.rscmd` contains:

```text
-newScene
-addFolder <job>\images
-align
-selectMaximalComponent
-setReconstructionRegionAuto
-calculateNormalModel
-unwrap
-calculateTexture
-save <job>\project.rsproj
-exportSelectedModel <job>\export\model.obj <job>\export_params.xml
-quit
```

## Viewer-ready model guidance

Keep the high-poly RealityScan export as the archive/reference artifact. Do not use a roughly 7M-face model directly in a browser viewer. Create a simplified web/demo export first, targeting **300k to 1M faces**, then export OBJ + MTL + textures as one ZIP and import it as `textured_mesh / realityscan / current_state` with notes such as `web/demo model`.

Structura AI v0.1 is a local capture-to-reconstruction prototype: upload photos or video, prepare frames, run COLMAP sparse reconstruction, track attempts, choose the best result, view a sparse building point cloud, and generate a cached scan report. The current demo proves a practical sparse reconstruction workflow without claiming a finished dense mesh or production inspection model.

## Demo Result

**South Building demo: 128/128 registered images, 85k sparse points**

- Dataset style: exterior/building photo set
- Matching mode: `Photo Exhaustive`
- Frame selection: `All frames`
- Sparse points: `85,105`
- Sparse quality: `Strong Sparse Reconstruction`
- Viewer mode: `Exterior / building scan`
- Recommended demo view: `Presentation mode`

## Demo Screenshots

![Dashboard](docs/screenshots/dashboard.png)

![Processing Summary](docs/screenshots/processing-summary.png)

![Sparse Building Preview](docs/screenshots/sparse-building-preview.png)

![Scan Report](docs/screenshots/scan-report.png)

## v0.1 Sparse Reconstruction Demo

- Local photo/video capture pipeline
- COLMAP sparse reconstruction
- Best attempt tracking
- Exterior building viewer
- Cached scan reports
- South Building result: `128/128 registered images, 85,105 sparse points`

This version produces sparse point cloud previews, not dense meshes or textured 3D models yet.

## Product direction

- v0.1 Sparse reconstruction demo
- External textured mesh and dense-cloud artifact management
- RealityScan OBJ/MTL/texture ZIP bundle import
- Reference vs. current-state readiness
- Future: aligned point-cloud/mesh distance analysis

## Legacy experiment: Nerfstudio / Gaussian Splat

Nerfstudio/Splatfacto was explored as an experimental visual-preview path. It is not the Structura product path: Gaussian Splats are not measurement-grade and are not used for progress comparison. Legacy endpoints and files remain for compatibility only.

- Requires Nerfstudio/Splatfacto installed outside Structura.
- Uses Structura COLMAP sparse output and registered images.
- Produces a Gaussian Splat export only when Nerfstudio training and export succeed.
- It is not a dense mesh.
- It is not used for progress measurement yet.
- In-browser splat rendering is a later milestone.

Optional environment variables:

```powershell
$env:NERFSTUDIO_PYTHON="C:\path\to\python.exe"
$env:NERFSTUDIO_NS_TRAIN="C:\path\to\ns-train.exe"
$env:NERFSTUDIO_NS_EXPORT="C:\path\to\ns-export.exe"
```

Windows setup helper:

```powershell
.\scripts\setup_nerfstudio_windows.ps1
```

On Windows, Splatfacto CUDA extension builds need the VS 2022 Build Tools C++ workload, CUDA 11.8 conda build packages, and a local CUDA 11.8 CUB header patch for the Windows SDK `small` macro collision. The setup helper applies the conda/package/header parts; install VS 2022 Build Tools first if `vcvars64.bat` is missing:

```powershell
winget install --id Microsoft.VisualStudio.2022.BuildTools --exact --silent --accept-package-agreements --accept-source-agreements
```

Known-good local paths after the helper installs Miniconda:

```powershell
$env:NERFSTUDIO_PYTHON="C:\Users\serfu\miniconda3\envs\nerfstudio\python.exe"
$env:NERFSTUDIO_NS_TRAIN="C:\Users\serfu\miniconda3\envs\nerfstudio\Scripts\ns-train.exe"
$env:NERFSTUDIO_NS_EXPORT="C:\Users\serfu\miniconda3\envs\nerfstudio\Scripts\ns-export.exe"
```

Legacy-only flow:

1. Run a successful sparse reconstruction and keep the best attempt selected.
2. Open Visual Preview and confirm diagnostics show Nerfstudio, `ns-train`, `ns-export`, and CUDA available.
3. Prepare the visual preview manifest. Structura creates `nerfstudio_dataset/images/` and `nerfstudio_dataset/sparse/0/`.
4. Train with Splatfacto from the Visual Preview page or API. Use `smoke` only to validate the pipeline, `demo` for portfolio screenshots, and `quality` when slower training is acceptable.
5. Export Gaussian Splat. Structura only marks export complete when a `.ply` file is produced.
6. Current limitation: browser Gaussian Splat rendering is pending; the exported `.ply` path and size are shown instead.

Training presets:

- `smoke`: 1 iteration, pipeline validation only.
- `quick`: 1000 iterations, fast preview.
- `demo`: 7000 iterations, recommended for meaningful portfolio screenshots.
- `quality`: 30000 iterations, slower but better.

## Features

- Photo/video capture upload
- FFmpeg-backed video frame extraction
- Uploaded photo normalization into reconstruction frames
- Frame selection modes: Balanced subset, All frames, Sharpest subset, Evenly spaced subset
- COLMAP sparse reconstruction
- Sparse reconstruction attempt tracking
- Best attempt scoring and default selection
- Sparse experiment sweep for comparing frame-selection strategies
- External dense point cloud / textured mesh artifact import
- RealityScan OBJ + MTL + texture ZIP bundle handling
- Exterior/building sparse point cloud viewer
- Manual viewer orientation save per attempt
- Presentation mode for clean demo screenshots
- Cached report generation that avoids reparsing large point clouds
- CUDA-aware dense readiness diagnostics
- Dense reconstruction endpoint kept available but de-emphasized when COLMAP lacks CUDA

## Honest Limitations

- Current output is a sparse point cloud preview.
- Gaussian Splat output is legacy preview-only and not measurement-grade.
- High-poly external meshes are managed artifacts; a heavy browser viewer is not implemented.
- Scale and orientation are arbitrary unless aligned manually in the viewer.
- Measurements are approximate prototype values.
- Dense stereo reconstruction realistically requires a CUDA-enabled COLMAP build on this machine.
- Mesh generation, textured model export, and GLB export are future milestones.

## Local Setup

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend URL: `http://127.0.0.1:8000`

Video frame extraction uses FFmpeg. The backend checks `ffmpeg` on PATH, then falls back to `imageio-ffmpeg` from `requirements.txt`.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL: `http://localhost:3000`

### COLMAP

Sparse reconstruction requires COLMAP on PATH or a configured COLMAP executable.

```powershell
colmap -h
Invoke-RestMethod http://127.0.0.1:8000/diagnostics
```

If diagnostics says COLMAP is installed `without CUDA`, sparse reconstruction can still work, but dense stereo may fail or be unavailable.

## Demo Flow

1. Start the backend and frontend.
2. Open `http://localhost:3000`.
3. Create a Building Scan project.
4. Upload the South Building photo set.
5. Process capture.
6. Run sparse reconstruction with `Photo Exhaustive` and `All frames`.
7. Open the viewer.
8. Select or confirm `Exterior / building scan`.
9. Align the sparse point cloud if needed and save the attempt orientation.
10. Enable `Presentation mode`.
11. Open the report.
12. Explain the result: `128/128 registered images, 85k sparse points`.
13. Process the South Building capture in RealityScan or another external photogrammetry engine.
14. Export OBJ + MTL + textures as one ZIP.
15. Import it into Model Artifacts as `textured_mesh` with `sourceTool = realityscan`.
16. Mark it `current_state`, then add a separate `finished_reference` artifact when available.
17. Review Measurement / Progress Readiness in the report.

## API Validation Commands

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/diagnostics
Invoke-RestMethod http://127.0.0.1:8000/projects
```

For a project:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/capture-summary"
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/reconstruction-summary"
Invoke-RestMethod "http://127.0.0.1:8000/visual-preview/diagnostics"
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/visual-preview-summary"
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/visual-preview/prepare" -Method Post
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/visual-preview/training-status"
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/visual-preview/splat-file/metadata"
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/report"
```

## Build Checks

```powershell
cd backend
.\.venv\Scripts\python -m compileall app

cd ..\frontend
npm run build
```

## Screenshots

Screenshot guidance is in `docs/SCREENSHOT_CHECKLIST.md`. Real screenshots should be saved under `docs/screenshots/`; no fake screenshots are included.
