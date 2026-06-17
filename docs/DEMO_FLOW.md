# Demo Flow

Use this flow for a portfolio or GitHub demo of Structura AI v0.1.

## Start Local Services

Backend:

```powershell
cd C:\Users\serfu\OneDrive\Desktop\projects\structura\backend
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd C:\Users\serfu\OneDrive\Desktop\projects\structura\frontend
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

## Demo Talk Track

Structura AI v0.1 turns a local capture into a COLMAP sparse reconstruction workflow. The South Building demo registered `128/128` images and generated about `85k` sparse points. The viewer is showing a sparse building point cloud preview, not a dense mesh or textured model.

The report is cached and uses precomputed reconstruction metadata, so it avoids reparsing the large point cloud on every report load. Dense reconstruction is shown as CUDA-aware readiness because the current local COLMAP build is installed without CUDA.
