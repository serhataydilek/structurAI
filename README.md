# Structura AI

Structura AI is an AI-assisted digital twin platform that turns building photos and videos into interactive 3D models for inspection, renovation, real estate, and construction progress tracking.

The final product vision is full building-scale digital twins. This MVP starts with controlled condo and interior captures because they are easier to test reliably: lighting, capture overlap, corners, and scan coverage can be reviewed in a smaller environment before expanding to exterior and full-building reconstruction.

## What This MVP Includes

- Next.js App Router frontend with TypeScript, Tailwind CSS, and React Three Fiber/Drei.
- FastAPI backend with SQLite metadata and local filesystem uploads.
- Project creation, media upload, real frame extraction, capture workspace preparation, viewer, annotations, and report flow.
- Empty reconstruction viewer state until real sparse or dense output exists.
- COLMAP sparse reconstruction integration for Phase 2A when COLMAP is available on PATH.
- No authentication, payments, teams, admin panels, dense reconstruction, mesh generation, or GLB export yet.

## Real Capture-Processing Milestone

This version now performs the first real capture-processing step:

- Real local upload of images and one optional video.
- Real video frame extraction with FFmpeg using Fast 1 FPS, Balanced 2 FPS, or Detailed 3 FPS modes.
- Uploaded images normalized into the same frame sequence as video frames.
- Per-project processing workspace under `backend/storage/processed/{project_id}/`.
- Frame thumbnails for preview in the processing page.
- Capture summary and report metadata, including frame count, selected FPS, sharpness metrics, blur warnings, and reconstruction readiness.
- Dashboard search, status filters, per-project deletion, and local data reset for development.

The interactive 3D viewer shows a real sparse point cloud after COLMAP succeeds. If no sparse or dense output exists, it shows an empty reconstruction state instead of a procedural room.

## Future Roadmap

The capture preparation pipeline is real, while 3D reconstruction is the next integration stage:

Phone Photos / Video -> Upload Service -> Frame Extraction -> 3D Reconstruction -> GLB Model Export -> Interactive Viewer -> AI Annotations & Reports

Future tools and stages:

- FFmpeg for frame extraction and media normalization.
- COLMAP for camera pose estimation and sparse reconstruction.
- OpenMVS for dense reconstruction.
- Blender CLI for cleanup, conversion, and GLB export.
- Segment Anything / object detection for AI-assisted annotations.

Next technical milestones:

- OpenMVS dense reconstruction.
- Blender GLB export.

## Phase 2A: COLMAP Sparse Reconstruction

Structura AI now includes the first sparse reconstruction integration point. After capture processing creates normalized frames, the backend can run:

- `colmap feature_extractor`
- `colmap sequential_matcher` for video-style frame sequences, or `colmap exhaustive_matcher` for photo sets
- `colmap mapper`

Sparse reconstruction outputs are written to:

`backend/storage/processed/{project_id}/reconstruction/colmap/`

That folder contains:

- `database.db`
- `sparse/`
- `logs/`

Check COLMAP availability before running sparse reconstruction:

```powershell
colmap -h
# or
COLMAP.bat -h
```

The app also exposes diagnostics:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/diagnostics
```

Expected limitations:

- Indoor scans may fail when walls are plain or low texture.
- Mirrors and glass hurt feature matching.
- Blurry frames reduce match quality.
- More overlap and more textured surfaces improve results.
- This phase does not run dense reconstruction, mesh generation, or GLB export.

Capture recommendations for indoor spaces:

- Move slowly through the room and keep the camera stable.
- Keep 60-80% overlap between adjacent views.
- Capture corners, door frames, furniture edges, posters, rugs, and other textured surfaces.
- Avoid blank walls, mirrors, glass, fast pans, and very dark rooms.
- Prefer a slow walkthrough video with Balanced 2 FPS first; use Detailed 3 FPS when the first sparse result is too thin.
- For photo-only captures, take many overlapping images from multiple angles.

Test flow:

1. Upload 80+ frames, a slow video with strong overlap, or a photo set with many overlapping views.
2. Process capture to extract/normalize frames.
3. Choose `Auto`, `Video Sequential`, or `Photo Exhaustive`, then click `Run Sparse Reconstruction`.
4. Inspect the reconstruction summary and logs.
5. Treat dense reconstruction / point cloud visualization as the next milestone.

## Phase 2B: Sparse Point Cloud Preview

After a successful COLMAP sparse reconstruction, Structura AI exports the sparse model to TXT using:

```powershell
COLMAP.bat model_converter --input_path <sparse-model> --output_path <exports> --output_type TXT
```

The backend parses `points3D.txt` and exposes the sparse points through:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/point-cloud"
```

The viewer switches modes automatically:

- `Sparse Scene Preview` when real COLMAP sparse points are available.
- `No Reconstruction Output Yet` when no sparse or dense output exists.

This is not a dense mesh or full building model. A sparse point cloud shows matched visual features and camera-derived structure from the uploaded capture. Dense reconstruction, mesh generation, and GLB export remain future milestones.

Sparse point clouds can look incomplete because COLMAP only keeps visual features it can match across frames. Plain walls, motion blur, poor lighting, repeated textures, mirrors, glass, and low overlap all reduce the number of reliable sparse points.

Phase 2B test flow:

1. Upload a capture with strong overlap, ideally 60+ frames or a slow video.
2. Process capture to extract frames.
3. Run sparse reconstruction.
4. Open the viewer.
5. Verify the viewer shows `Sparse Scene Preview` instead of an empty reconstruction state.

## Sparse Scene Preview

Sparse Scene Preview is a readability layer on top of real COLMAP sparse reconstruction output. It keeps the actual sparse feature points, then estimates scene context from those points so the capture is easier to inspect before dense reconstruction or mesh generation is available.

The backend exposes this analysis through:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/scene-analysis"
```

The response includes:

- sparse point count
- raw and robust bounding box
- center and scale used by the viewer
- estimated floor level from the low percentile of sparse point height
- estimated room scaffold width, depth, and height
- best-effort camera path from COLMAP `images.txt` when available
- confidence label and warnings

Important limitations:

- Sparse points are real reconstruction output.
- Room bounds and floor are estimated from sparse features, not measured geometry.
- This is not a generated mesh, textured model, or final digital twin.
- Dense reconstruction still requires a CUDA-enabled COLMAP build on this machine, or another dense/visual preview pipeline.

Viewer controls let you show or hide sparse points, estimated room bounds, estimated floor, camera path, and the floor/grid reference.

## Phase 2C: Sparse Reconstruction Quality

Phase 2C improves sparse reconstruction reliability and readability without adding dense reconstruction or mesh generation.

Video extraction modes:

- `Fast`: 1 FPS for quick processing.
- `Balanced`: 2 FPS, the default and recommended first pass.
- `Detailed`: 3 FPS for more COLMAP input frames when the capture is sparse or blurry.

Frame quality analysis:

- The backend computes a lightweight Pillow-based sharpness score for extracted frames.
- Capture summaries include average sharpness, blurry frame count, blurry percentage, and a readiness label.
- Readiness labels are based on frame count: fewer than 30 frames is `Poor Capture`, 30-80 is `Usable Prototype Capture`, and 80+ is `Good Reconstruction Candidate`.
- High blur downgrades readiness by one level.

Matching modes:

- `Auto`: uses sequential matching when a video was uploaded and exhaustive matching for photo-only captures.
- `Video Sequential`: runs `colmap sequential_matcher`.
- `Photo Exhaustive`: runs `colmap exhaustive_matcher`.

Frame selection modes:

- `Balanced subset` is the recommended default. It caps video-style inputs to 120 selected frames, keeps coverage across the full capture, and prefers sharper frames when sharpness scores are available.
- `All frames` keeps the old behavior and sends every extracted frame to COLMAP. Use it for small, deliberate photo sets or short captures where most frames are sharp and useful.
- `Sharpest subset` chooses the sharpest scored frames up to the 120-frame cap. Use it when blur is the main problem, but coverage is still broad enough.
- `Evenly spaced subset` samples across the full timeline up to the 120-frame cap. Use it when sharpness scores are unavailable or when temporal coverage matters more than per-frame sharpness.

Frame selection matters because more frames are not always better for COLMAP. Many blurry, redundant, or weakly matched frames can make feature matching worse than a smaller, cleaner input set.

Sparse experiment sweep:

- Start with a normal `Balanced subset` sparse reconstruction.
- If the output is weak, run `Sparse Experiment Sweep` from the processing or viewer page.
- The sweep runs several controlled sparse attempts without deleting prior attempts: Balanced subset + Video Sequential, Sharpest subset + Video Sequential, and Evenly spaced subset + Video Sequential.
- Structura keeps all attempts and continues using the best-scoring sparse attempt by default.
- Registration ratio is reported against selected frames first, for example `44/120 selected frames registered`; source-frame count is shown separately because the reconstruction did not use every extracted frame.

Capture mode guidance:

- For video scan mode, record 60-90 seconds, use Balanced 2 FPS, use Video Sequential matching, and use Balanced subset frame selection.
- For photo set mode, take 40-80 sharp images, keep 60-70% overlap, use Photo Exhaustive matching, and use All frames or Balanced subset frame selection.
- If video sparse reconstruction is poor, switch to a sharp photo set. Keep the same objects visible across multiple photos, capture corners, doors, windows, furniture, and textured objects, and avoid blank walls, mirrors, glass, and shiny surfaces.
- When sparse quality is `Poor Sparse Reconstruction`, Structura now treats dense reconstruction as secondary or experimental. The primary next action is better capture, with another sparse sweep as the secondary option.

How to improve sparse reconstruction quality:

- Use Detailed 3 FPS for video captures with fast camera motion or thin point clouds.
- Move slower and avoid fast turns.
- Improve lighting and reduce motion blur.
- Add textured objects or capture areas with natural feature points.
- Avoid mirrors, glass, blank walls, and repetitive surfaces.
- Try `Video Sequential` for walkthrough video and `Photo Exhaustive` for curated photo sets.

The next milestone is Phase 3A COLMAP dense point-cloud reconstruction. Mesh and GLB export remain later milestones.

## Phase 3A: Dense Point Cloud Reconstruction

Structura AI can now run COLMAP dense reconstruction after sparse reconstruction completes. The backend runs:

- `colmap image_undistorter`
- `colmap patch_match_stereo`
- `colmap stereo_fusion`

Dense outputs are written under:

`backend/storage/processed/{project_id}/reconstruction/colmap/dense/`

The fused dense point cloud is expected at:

`backend/storage/processed/{project_id}/reconstruction/colmap/dense/workspace/fused.ply`

The backend exposes dense preview points through:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/dense-point-cloud"
```

Dense reconstruction output is still a point cloud. It is not a mesh, not a textured model, and not a final digital twin. Mesh generation and GLB export are the next milestone.

Dense reconstruction may be slow without CUDA. CPU-only COLMAP can take a long time on indoor video captures, and weak sparse reconstruction usually produces weak dense reconstruction.

Recommended capture for dense reconstruction:

- 60-90 second slow indoor video.
- Balanced 2 FPS for the first run, Detailed 3 FPS when sparse points are thin.
- Video Sequential matching for walkthrough video.
- Good lighting and stable camera motion.
- Textured surfaces, corners, furniture edges, rugs, posters, and non-reflective objects.
- Avoid mirrors, glass, blank walls, fast pans, and dark rooms.

Phase 3A test flow:

1. Process a high-overlap capture.
2. Run sparse reconstruction and confirm sparse points exist.
3. Click `Run Dense Reconstruction`.
4. Open the viewer.
5. Verify the viewer uses `Dense Point Cloud Preview` when dense points are available.
6. Treat mesh / GLB export as the next milestone.

## Local Setup

### Backend

```powershell
cd C:\Users\serfu\OneDrive\Desktop\projects\structura\backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend URL: `http://127.0.0.1:8000`

Video frame extraction uses FFmpeg. The backend first checks for `ffmpeg` on PATH, then falls back to the bundled `imageio-ffmpeg` dependency installed from `requirements.txt`.

```powershell
ffmpeg -version
```

If neither system FFmpeg nor `imageio-ffmpeg` is available, image-only processing still works, but video processing returns a clear backend error explaining the missing dependency.

### Frontend

```powershell
cd C:\Users\serfu\OneDrive\Desktop\projects\structura\frontend
npm install
npm run dev
```

Frontend URL: `http://localhost:3000`

## Screenshots

Screenshot placeholders live in `docs/screenshots/`. Add product screenshots there as the interface stabilizes.

Suggested screenshots:

- Landing page
- New scan project
- Upload media
- Capture processing pipeline
- Capture review and sparse reconstruction summary
- No reconstruction output state
- Generated capture report

## Application Workflow

1. Open `http://localhost:3000`.
2. Create a new scan project, preferably using `Condo Interior` for the controlled MVP workflow.
3. Upload multiple images and optionally one video.
4. Choose an extraction mode and run capture processing:
   - Upload received
   - Extracting frames
   - Preparing reconstruction workspace
   - Capture analysis complete
   - Ready for reconstruction
5. Review extracted frame thumbnails, warnings, and reconstruction readiness.
6. Choose a matching mode and run sparse reconstruction if COLMAP is installed.
7. Run dense reconstruction after sparse reconstruction completes.
8. Open the viewer. Dense point cloud is preferred, sparse point cloud is the fallback, and an empty reconstruction state is shown when no reconstruction exists.
9. Add manual annotations.
10. Generate the capture report.

## Current Prototype Limitation

- Sparse and dense point-cloud reconstruction are available when COLMAP is installed, but neither output is a mesh or full digital twin.
- The viewer shows an empty reconstruction state when no reconstructed point cloud exists.
- The backend processing service is structured so OpenMVS and Blender CLI can be integrated later.
- Measurements are approximate in this prototype.
- Mesh generation and GLB export are not yet enabled in this build.

## API Validation Commands

Run these from PowerShell after the backend is running.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health

$project = Invoke-RestMethod -Method Post http://127.0.0.1:8000/projects `
  -ContentType "application/json" `
  -Body '{"name":"Condo Capture Validation","siteType":"Condo Interior","description":"Controlled interior capture validation"}'

$project
Invoke-RestMethod http://127.0.0.1:8000/projects

$pngPath = Join-Path $env:TEMP 'structura-sample.png'
[IO.File]::WriteAllBytes($pngPath, [Convert]::FromBase64String('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lZ8F7QAAAABJRU5ErkJggg=='))
Add-Type -AssemblyName System.Net.Http
$client = [System.Net.Http.HttpClient]::new()
$form = [System.Net.Http.MultipartFormDataContent]::new()
$fileContent = [System.Net.Http.ByteArrayContent]::new([System.IO.File]::ReadAllBytes($pngPath))
$fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('image/png')
$form.Add($fileContent, 'files', 'structura-sample.png')
$uploadResponse = $client.PostAsync("http://127.0.0.1:8000/projects/$($project.id)/media", $form).Result
$uploadResponse.Content.ReadAsStringAsync().Result

Invoke-RestMethod -Method Post "http://127.0.0.1:8000/projects/$($project.id)/annotations" `
  -ContentType "application/json" `
  -Body '{"text":"Check scan density near entry wall"}'

Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/annotations"
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/projects/$($project.id)/process"
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/status"
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/frames"
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/capture-summary"
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/reconstruction-summary"
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/report"
Invoke-RestMethod -Method Delete "http://127.0.0.1:8000/projects/$($project.id)"
```

After processing reaches `Ready`, fetch the model URL:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/model"
```

For upload validation, use the UI or send a real image/video file with multipart form field name `files`. Unsupported files are rejected, and only one video is allowed per project.

Local development reset is available only in local/dev mode:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/dev/reset
```

## Build Checks

```powershell
cd C:\Users\serfu\OneDrive\Desktop\projects\structura\backend
.\.venv\Scripts\python -m compileall app

cd C:\Users\serfu\OneDrive\Desktop\projects\structura\frontend
npm run build
```
