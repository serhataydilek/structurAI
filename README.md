# Structura AI

Structura AI is an AI-assisted digital twin platform that turns building photos and videos into interactive 3D models for inspection, renovation, real estate, and construction progress tracking.

The final product vision is full building-scale digital twins. This MVP starts with controlled condo and interior captures because they are easier to test reliably: lighting, capture overlap, corners, and scan coverage can be reviewed in a smaller environment before expanding to exterior and full-building reconstruction.

## What This MVP Includes

- Next.js App Router frontend with TypeScript, Tailwind CSS, and React Three Fiber/Drei.
- FastAPI backend with SQLite metadata and local filesystem uploads.
- Project creation, media upload, simulated processing, viewer, annotations, and report flow.
- Procedural 3D interior preview when `/models/sample-condo.glb` is not available.
- No authentication, payments, teams, admin panels, or real COLMAP/OpenMVS processing yet.

## Future Roadmap

The current pipeline is simulated, but the backend is structured so real reconstruction stages can be added later:

Phone Photos / Video -> Upload Service -> Frame Extraction -> 3D Reconstruction -> GLB Model Export -> Interactive Viewer -> AI Annotations & Reports

Future tools and stages:

- FFmpeg for frame extraction and media normalization.
- COLMAP for camera pose estimation and sparse reconstruction.
- OpenMVS for dense reconstruction.
- Blender CLI for cleanup, conversion, and GLB export.
- Segment Anything / object detection for AI-assisted annotations.

## Local Setup

### Backend

```powershell
cd C:\Users\serfu\OneDrive\Desktop\projects\structura\backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend URL: `http://127.0.0.1:8000`

### Frontend

```powershell
cd C:\Users\serfu\OneDrive\Desktop\projects\structura\frontend
npm install
npm run dev
```

Frontend URL: `http://localhost:3000`

## Demo Screenshots

Demo screenshot placeholders live in `docs/screenshots/`. Add captured mentor-demo screenshots there as the UI stabilizes.

Suggested screenshots:

- Landing page
- New scan project
- Upload media
- Simulated processing pipeline
- Interactive 3D viewer
- Generated report

## Mentor Demo Flow

1. Landing page
2. New scan project
3. Upload media
4. Simulated processing pipeline
5. Interactive 3D viewer
6. Add annotations
7. Generate report

## Demo Walkthrough

1. Open `http://localhost:3000`.
2. Click `Start Scan Demo`.
3. Create a new scan project, preferably using `Condo Interior`.
4. Upload multiple images and optionally one video.
5. Watch the simulated processing pipeline:
   - Upload received
   - Extracting frames
   - Estimating camera positions
   - Generating point cloud
   - Building 3D model
   - Exporting digital twin
6. Open the 3D viewer.
7. Review the prototype digital twin preview or `/models/sample-condo.glb` if a GLB is added later.
8. Add manual annotations.
9. Generate the scan summary / export report.

## Current Prototype Limitation

- The MVP currently uses a procedural 3D interior fallback instead of real reconstruction.
- The backend processing service is structured so FFmpeg, COLMAP, OpenMVS, and Blender CLI can be integrated later.
- Measurements are approximate in this prototype.

## API Validation Commands

Run these from PowerShell after the backend is running.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health

$project = Invoke-RestMethod -Method Post http://127.0.0.1:8000/projects `
  -ContentType "application/json" `
  -Body '{"name":"Mentor Condo Demo","siteType":"Condo Interior","description":"Controlled interior scan demo"}'

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
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/report"
```

After processing reaches `Ready`, fetch the model URL:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/projects/$($project.id)/model"
```

For upload validation, use the UI or send a real image/video file with multipart form field name `files`. Unsupported files are rejected, and only one video is allowed per project.

## Build Checks

```powershell
cd C:\Users\serfu\OneDrive\Desktop\projects\structura\backend
.\.venv\Scripts\python -m compileall app

cd C:\Users\serfu\OneDrive\Desktop\projects\structura\frontend
npm run build
```
