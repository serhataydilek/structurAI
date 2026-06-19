# Demo Flow

Use this flow for a portfolio or GitHub demo of Structura AI v0.1.

## Start Local Services

Backend:

```powershell
cd backend
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:3000`.

## South Building Demo

1. Create a Building Scan project.
2. Upload the South Building photo set.
3. Process the capture.
4. Run sparse reconstruction.
5. For the South Building photo set, use `Photo Exhaustive` matching and `All frames`.
6. Open the viewer.
7. Use `Exterior / building scan` mode.
8. Align the point cloud if needed and save the orientation for the attempt.
9. Enable `Presentation mode`.
10. Open the report.
11. Capture or review screenshots in `docs/screenshots/`:
    - `dashboard.png`
    - `project-overview.png`
    - `processing-summary.png`
    - `sparse-building-preview.png`
    - `scan-report.png`

## Demo Talk Track

Structura AI v0.1 turns a local capture into a COLMAP sparse reconstruction workflow. The South Building demo registered `128/128` images and generated about `85k` sparse points. The viewer is showing a sparse building point cloud preview, not a dense mesh or textured model.

The report is cached and uses precomputed reconstruction metadata, so it avoids reparsing the large point cloud on every report load. Dense reconstruction is shown as CUDA-aware readiness because the current local COLMAP build is installed without CUDA.
# Visual Preview: Nerfstudio/Splatfacto

Dense reconstruction remains de-emphasized unless COLMAP has CUDA support. The Visual Preview path uses the successful South Building sparse attempt as input for Nerfstudio Splatfacto.

1. Start the backend with `NERFSTUDIO_PYTHON`, `NERFSTUDIO_NS_TRAIN`, and `NERFSTUDIO_NS_EXPORT` set.
2. Call `/visual-preview/diagnostics` and confirm CUDA, `ns-train`, and `ns-export` are available.
3. Open the South Building project and prepare Visual Preview.
4. Confirm the prepared dataset has `nerfstudio_dataset/images/` and `nerfstudio_dataset/sparse/0/` with COLMAP cameras, images, and points files.
5. Start training from the Visual Preview page. Use `Demo quality, 7000 iters` for portfolio screenshots. The request returns immediately and status/logs update in the background.
6. Export after `config.yml` is available.
7. Confirm the success state says `Gaussian Splat exported successfully.`
8. Download the exported `splat.ply`.
9. Open the file in a compatible external Gaussian Splat viewer such as SuperSplat or Polycam.

This is a real Nerfstudio/Splatfacto export from the sparse reconstruction. Browser splat rendering inside Structura is pending and must not be faked.

Training presets:

- `Smoke test, 1 iter`: validates the pipeline only; output will be blurry or incomplete.
- `Quick preview, 1000 iters`: fast preview.
- `Demo quality, 7000 iters`: recommended for portfolio screenshots.
- `High quality, 30000 iters`: slower but better.
