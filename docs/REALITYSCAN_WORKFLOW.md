# RealityScan / RealityCapture workflow

Use this workflow to create a measurement-oriented external artifact from the South Building image set. Structura's Gaussian Splat exports are preview-only; export a dense point cloud or textured mesh from an external photogrammetry application for progress work.

## Dataset

Import all 128 images from:

```text
C:\Users\serfu\OneDrive\Desktop\projects\structura\backend\storage\processed\9891a2df-2e2b-4511-81b5-32881fb2d4e6\frames
```

## RealityScan / RealityCapture

1. Open the **Epic Games Launcher** and sign in with an Epic account.
2. Search the official Epic catalog/library for **RealityScan** or **RealityCapture**, then select **Install**. Do not use third-party installers.
3. Open the installed application and create a new project.
4. Choose **Add Images** (or the equivalent import action) and select the dataset folder above. Confirm all 128 images are selected.
5. Run **Align Images**. Inspect the aligned cameras and remove only clearly unaligned or erroneous images before continuing.
6. Run the application's model/reconstruction step at an appropriate quality setting. This may take significant time and disk space.
7. If available, run texture generation after the mesh is complete.
8. Export in this order of preference:
   - **OBJ textured mesh** (include its material/texture files) for a client-quality surface model.
   - **PLY dense point cloud** when the analysis workflow needs a point cloud.
9. In Structura, open **Model Artifacts** and import the exported primary file:
   - OBJ: `artifactType = textured_mesh`
   - PLY dense cloud: `artifactType = dense_point_cloud`
   - `sourceTool = realitycapture` (use the closest available RealityScan/RealityCapture source label)
   - `role = current_state`

Do not import a Nerfstudio/Splatfacto `splat.ply` as a dense point cloud. Gaussian Splats are visual-preview artifacts, not measurement-grade geometry.

## Metashape fallback (official trial)

If RealityScan/RealityCapture is unavailable in Epic Launcher, use the official **Agisoft Metashape Professional** trial:

1. Visit Agisoft's official download page and download the Windows installer for the 30-day trial.
2. Install it and activate the trial using Agisoft's official activation flow.
3. Create a new chunk, use **Add Photos**, and select the dataset folder above.
4. Run **Align Photos**, then **Build Depth Maps** and **Build Model** or **Build Point Cloud**.
5. Build texture for a mesh when required.
6. Export an OBJ textured mesh first, or a PLY dense point cloud second.
7. Import into Structura with `sourceTool = metashape` and `role = current_state`.

## Comparison note

To make a real comparison, separately import a finished/reference dense cloud or mesh and mark it `finished_reference`. Structura records the comparison relationship, but alignment and distance analysis still need CloudCompare or a future internal engine.
