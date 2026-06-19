import type { Annotation, CaptureSummary, Diagnostics, ExtractionFpsMode, FramePreview, FrameSelectionMode, FrameSelectionPreview, PointCloudResponse, PreviewMode, ProcessingStatus, Project, ReconstructionMatchingMode, ReconstructionSummary, Report, SceneAnalysis, SparseSweepResponse, ViewerTransform, VisualPreviewDiagnostics, VisualPreviewPreset, VisualPreviewSplatMetadata, VisualPreviewSummary, VisualPreviewTrainingStatusResponse } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...init?.headers
      },
      cache: "no-store"
    });
  } catch (error) {
    throw new Error(`Cannot reach Structura API at ${API_BASE}. Make sure the backend is running on port 8000.`);
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = error.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.summary?.denseLastError ?? detail?.summary?.denseErrorMessage ?? detail?.summary?.errorMessage ?? detail?.message ?? response.statusText;
    throw new Error(message ?? "Request failed");
  }

  return response.json() as Promise<T>;
}

export function listProjects() {
  return request<Project[]>("/projects");
}

export function getProject(projectId: string) {
  return request<Project>(`/projects/${projectId}`);
}

export function getDiagnostics() {
  return request<Diagnostics>("/diagnostics");
}

export function getVisualPreviewDiagnostics() {
  return request<VisualPreviewDiagnostics>("/visual-preview/diagnostics");
}

export function deleteProject(projectId: string) {
  return request<{ status: string; projectId: string }>(`/projects/${projectId}`, {
    method: "DELETE"
  });
}

export function resetDevData() {
  return request<{ status: string }>("/dev/reset", {
    method: "POST"
  });
}

export function createProject(payload: { name: string; siteType: string; description: string }) {
  return request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function uploadMedia(projectId: string, files: File[]) {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  return request<{ count: number }>(`/projects/${projectId}/media`, {
    method: "POST",
    body: form
  });
}

export function startProcessing(projectId: string, options?: { extractionFpsMode?: ExtractionFpsMode }) {
  return request<ProcessingStatus>(`/projects/${projectId}/process`, {
    method: "POST",
    body: JSON.stringify({ extractionFpsMode: options?.extractionFpsMode ?? "Balanced" })
  });
}

export function getProcessingStatus(projectId: string) {
  return request<ProcessingStatus>(`/projects/${projectId}/status`);
}

export function getFrames(projectId: string) {
  return request<FramePreview[]>(`/projects/${projectId}/frames`);
}

export function getCaptureSummary(projectId: string) {
  return request<CaptureSummary>(`/projects/${projectId}/capture-summary`);
}

export function runSparseReconstruction(projectId: string, options?: { matchingMode?: ReconstructionMatchingMode; frameSelectionMode?: FrameSelectionMode }) {
  return request<ReconstructionSummary>(`/projects/${projectId}/reconstruct/sparse`, {
    method: "POST",
    body: JSON.stringify({ matchingMode: options?.matchingMode, frameSelectionMode: options?.frameSelectionMode })
  });
}

export function runSparseReconstructionSweep(projectId: string) {
  return request<SparseSweepResponse>(`/projects/${projectId}/reconstruct/sparse/sweep`, {
    method: "POST"
  });
}

export function previewFrameSelection(projectId: string, mode: FrameSelectionMode) {
  return request<FrameSelectionPreview>(`/projects/${projectId}/frame-selection/preview`, {
    method: "POST",
    body: JSON.stringify({ mode })
  });
}

export function runDenseReconstruction(projectId: string) {
  return request<ReconstructionSummary>(`/projects/${projectId}/reconstruct/dense`, {
    method: "POST"
  });
}

export function getReconstructionSummary(projectId: string) {
  return request<ReconstructionSummary>(`/projects/${projectId}/reconstruction-summary`);
}

export function getVisualPreviewSummary(projectId: string) {
  return request<VisualPreviewSummary>(`/projects/${projectId}/visual-preview-summary`);
}

export function prepareVisualPreview(projectId: string) {
  return request<VisualPreviewSummary>(`/projects/${projectId}/visual-preview/prepare`, {
    method: "POST"
  });
}

export function trainVisualPreview(projectId: string, payload?: { visualPreviewId?: string; attemptId?: string; maxIterations?: number; trainingPreset?: VisualPreviewPreset; preset?: VisualPreviewPreset }) {
  return request<VisualPreviewTrainingStatusResponse>(`/projects/${projectId}/visual-preview/train`, {
    method: "POST",
    body: JSON.stringify(payload ?? { trainingPreset: "demo" })
  });
}

export function getVisualPreviewTrainingStatus(projectId: string) {
  return request<VisualPreviewTrainingStatusResponse>(`/projects/${projectId}/visual-preview/training-status`);
}

export function exportVisualPreview(projectId: string, visualPreviewId?: string) {
  return request<VisualPreviewTrainingStatusResponse>(`/projects/${projectId}/visual-preview/export`, {
    method: "POST",
    body: JSON.stringify({ visualPreviewId })
  });
}

export function getVisualPreviewSplatMetadata(projectId: string, visualPreviewId?: string) {
  const query = visualPreviewId ? `?visual_preview_id=${encodeURIComponent(visualPreviewId)}` : "";
  return request<VisualPreviewSplatMetadata>(`/projects/${projectId}/visual-preview/splat-file/metadata${query}`);
}

export function visualPreviewSplatDownloadUrl(projectId: string, visualPreviewId?: string) {
  const query = visualPreviewId ? `?visual_preview_id=${encodeURIComponent(visualPreviewId)}` : "";
  return `${API_BASE}/projects/${projectId}/visual-preview/splat-file${query}`;
}

export function getPointCloud(projectId: string, maxPoints = 50000, attemptId?: string) {
  const attemptParam = attemptId ? `&attempt_id=${encodeURIComponent(attemptId)}` : "";
  return request<PointCloudResponse>(`/projects/${projectId}/point-cloud?max_points=${maxPoints}${attemptParam}`);
}

export function getDensePointCloud(projectId: string, maxPoints = 100000) {
  return request<PointCloudResponse>(`/projects/${projectId}/dense-point-cloud?max_points=${maxPoints}`);
}

export function getSceneAnalysis(projectId: string, attemptId?: string) {
  const attemptParam = attemptId ? `?attempt_id=${encodeURIComponent(attemptId)}` : "";
  return request<SceneAnalysis>(`/projects/${projectId}/scene-analysis${attemptParam}`);
}

export function getModel(projectId: string) {
  return request<{ modelUrl: string }>(`/projects/${projectId}/model`);
}

export function listAnnotations(projectId: string) {
  return request<Annotation[]>(`/projects/${projectId}/annotations`);
}

export function addAnnotation(projectId: string, text: string) {
  return request<Annotation>(`/projects/${projectId}/annotations`, {
    method: "POST",
    body: JSON.stringify({ text })
  });
}

export function getReport(projectId: string) {
  return request<Report>(`/projects/${projectId}/report`);
}

export function saveAttemptViewerTransform(projectId: string, attemptId: string, transform: ViewerTransform, previewMode: PreviewMode) {
  return request(`/projects/${projectId}/attempts/${attemptId}/viewer-transform`, {
    method: "POST",
    body: JSON.stringify({ ...transform, previewMode })
  });
}
