# Structura AI

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

## Features

- Photo/video capture upload
- FFmpeg-backed video frame extraction
- Uploaded photo normalization into reconstruction frames
- Frame selection modes: Balanced subset, All frames, Sharpest subset, Evenly spaced subset
- COLMAP sparse reconstruction
- Sparse reconstruction attempt tracking
- Best attempt scoring and default selection
- Sparse experiment sweep for comparing frame-selection strategies
- Exterior/building sparse point cloud viewer
- Manual viewer orientation save per attempt
- Presentation mode for clean demo screenshots
- Cached report generation that avoids reparsing large point clouds
- CUDA-aware dense readiness diagnostics
- Dense reconstruction endpoint kept available but de-emphasized when COLMAP lacks CUDA

## Honest Limitations

- Current output is a sparse point cloud preview.
- It is not a dense mesh yet.
- It is not a textured model yet.
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
