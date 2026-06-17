# Release Checklist

Run this before presenting or tagging a portfolio demo build.

- Backend compile check passes:
  `cd backend; .\.venv\Scripts\python -m compileall app`
- Frontend build passes:
  `cd frontend; npm run build`
- `/diagnostics` returns COLMAP availability and CUDA/dense readiness.
- South Building project loads.
- Viewer loads the sparse building point cloud.
- Presentation mode works.
- Report loads quickly and shows cached summary data.
- Report shows `128/128 registered images` and about `85k` sparse points for the South Building demo.
- Screenshot files exist under `docs/screenshots/` and match the current UI.
- README screenshot links point to existing files.
- Failed or empty attempts are not presented as the main result.
- Dense reconstruction is not described as available when diagnostics says COLMAP lacks CUDA.
- No fake dense reconstruction claims remain.
- No misleading mesh, textured model, complete production model, or measurement-accurate wording remains.
