import type { Annotation, ProcessingStatus, Project, Report } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers
    },
    cache: "no-store"
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail ?? "Request failed");
  }

  return response.json() as Promise<T>;
}

export function listProjects() {
  return request<Project[]>("/projects");
}

export function getProject(projectId: string) {
  return request<Project>(`/projects/${projectId}`);
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

export function startProcessing(projectId: string) {
  return request<ProcessingStatus>(`/projects/${projectId}/process`, { method: "POST" });
}

export function getProcessingStatus(projectId: string) {
  return request<ProcessingStatus>(`/projects/${projectId}/status`);
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
