# Structura AI Mentor Demo Script

## 2-Minute Presentation

Hi, this is Structura AI. Version 0.1 is a local capture-to-COLMAP prototype that turns building photos or video into a sparse point cloud preview, tracks reconstruction attempts, and generates a scan report.

For this demo, I use the South Building photo set because it proves the exterior/building workflow with a real sparse reconstruction result.

I will start on the landing page, then create a new Building Scan project. The project form captures the project name, site or building type, and a short description.

Next, I upload scan media. The upload screen supports multiple images and an optional single video, and it includes capture guidance such as moving slowly, keeping 60-80% overlap, capturing corners, avoiding mirrors and glass, using good lighting, and capturing from multiple angles.

After upload, Structura AI prepares the reconstruction workspace. Image uploads are normalized into frames, and videos use FFmpeg frame extraction.

Once ready, I run COLMAP sparse reconstruction. The verified South Building result registered `128/128` images and generated about `85k` sparse points.

I then open the viewer, use Exterior / Building mode, and enable Presentation mode. This is a sparse building point cloud preview, not a dense mesh or textured model.

Finally, I generate the report. It summarizes the capture, best sparse attempt, reconstruction quality, annotations, dense readiness, and prototype limitations. The key limitation is honest: dense reconstruction requires a CUDA-enabled COLMAP build, and this version does not produce a dense mesh yet.
