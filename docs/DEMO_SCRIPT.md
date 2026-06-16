# Structura AI Mentor Demo Script

## 2-Minute Presentation

Hi, this is Structura AI. The product vision is an AI-assisted digital twin platform that turns building photos and videos into interactive 3D models for inspection, renovation, real estate, and construction progress tracking.

For this MVP, I narrowed the first controlled test case to condo and interior captures. That keeps the capture environment easier to validate while still proving the workflow needed for future building-scale digital twins.

I will start on the landing page, then create a new scan project. The project form captures the project name, site or building type, and a short description. For this demo, I will use a condo interior because it represents the first controlled MVP target.

Next, I upload scan media. The upload screen supports multiple images and an optional single video, and it includes capture guidance such as moving slowly, keeping 60-80% overlap, capturing corners, avoiding mirrors and glass, using good lighting, and capturing from multiple angles.

After upload, Structura AI runs a simulated processing pipeline: upload received, extracting frames, estimating camera positions, generating point cloud, building 3D model, and exporting the digital twin. The backend tracks deterministic progress and marks the project ready.

Once ready, I open the interactive 3D viewer. The current prototype shows a procedural digital twin preview when no generated GLB exists. The viewer includes orbit controls, lighting, project metadata, and inspection annotations. I can add a manual note and store it through the backend.

Finally, I generate the report. It summarizes the project name, uploaded media count, processing status, detected output, annotations, and prototype limitations. The important limitation is that measurements are approximate today, and real reconstruction will come later through FFmpeg, COLMAP, OpenMVS, and Blender CLI.

The key takeaway is that this MVP demonstrates the end-to-end product workflow now, while keeping the backend and UI ready for real reconstruction stages in future phases.
