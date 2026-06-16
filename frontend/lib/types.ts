export type ProjectStatus = "Draft" | "Processing" | "Ready";

export type Project = {
  id: string;
  name: string;
  site_type: string;
  description: string;
  scan_type: "Interior Prototype" | "Building Scan";
  status: ProjectStatus;
  created_at: string;
  processing_started_at?: string | null;
  media?: MediaItem[];
  mediaCount?: number;
};

export type MediaItem = {
  id: string;
  project_id: string;
  filename: string;
  original_filename: string;
  content_type: string;
  media_type: "image" | "video";
  size_bytes: number;
  created_at: string;
};

export type ProcessingStatus = {
  projectId: string;
  status: ProjectStatus;
  progress: number;
  currentStep: string;
  steps: string[];
};

export type Annotation = {
  id: string;
  project_id: string;
  text: string;
  created_at: string;
};

export type Report = {
  projectName: string;
  projectId: string;
  uploadedMediaCount: number;
  processingStatus: ProjectStatus;
  detectedOutput: string;
  annotations: Annotation[];
  limitations: string[];
};
