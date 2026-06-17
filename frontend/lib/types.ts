export type ProjectStatus =
  | "Draft"
  | "Media Uploaded"
  | "Processing"
  | "Ready"
  | "Reconstructing Sparse Model"
  | "Sparse Reconstruction Complete"
  | "Sparse Reconstruction Failed"
  | "Dense Reconstruction Running"
  | "Dense Reconstruction Complete"
  | "Dense Reconstruction Failed";

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
  extractedFrameCount?: number | null;
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
  nextStep?: string | null;
  extractedFrameCount?: number;
  selectedFpsMode?: ExtractionFpsMode;
  extractionFps?: number;
  averageSharpness?: number | null;
  blurryFrameCount?: number;
  blurryFramePercentage?: number;
  sharpnessAvailable?: boolean;
  warnings?: string[];
  workspacePrepared?: boolean;
  readinessLabel?: ReadinessLabel;
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
  captureMetadata?: CaptureSummary;
  reconstructionMetadata?: ReconstructionSummary;
  warnings?: string[];
  annotations: Annotation[];
  limitations: string[];
};

export type Diagnostics = {
  product: string;
  colmapAvailable: boolean;
  colmapPath: string | null;
  colmapVersion: string | null;
  colmapCudaHint: string | null;
  denseReconstructionLikelyAvailable: boolean | "unknown";
  colmap: {
    colmapAvailable: boolean;
    colmapPath: string | null;
    colmapVersion: string | null;
    colmapCudaHint: string | null;
    denseReconstructionLikelyAvailable: boolean | "unknown";
  };
};

export type ReadinessLabel = "Poor Capture" | "Usable Prototype Capture" | "Good Reconstruction Candidate";
export type ExtractionFpsMode = "Fast" | "Balanced" | "Detailed";
export type ReconstructionMatchingMode = "Auto" | "Video Sequential" | "Photo Exhaustive";

export type FramePreview = {
  filename: string;
  frameUrl: string;
  thumbnailUrl: string;
};

export type CaptureSummary = {
  projectId: string;
  uploadedMediaCount: number;
  extractedFrameCount: number;
  imageCount: number;
  videoCount: number;
  workspacePrepared: boolean;
  workspacePath: string | null;
  extractionMethod: string | null;
  selectedFpsMode: ExtractionFpsMode;
  extractionFps: number;
  averageSharpness: number | null;
  blurryFrameCount: number;
  blurryFramePercentage: number;
  sharpnessAvailable: boolean;
  warnings: string[];
  nextStep: string | null;
  reconstructionReadiness: string;
  readinessLabel: ReadinessLabel;
};

export type ReconstructionSummary = {
  projectId?: string;
  status: string;
  sparseStatus?: string;
  denseStatus?: string;
  colmapAvailable?: boolean;
  colmapPath?: string | null;
  colmapVersion?: string | null;
  colmapCudaHint?: string | null;
  denseReconstructionLikelyAvailable?: boolean | "unknown";
  inputFrameCount: number;
  selectedFpsMode?: ExtractionFpsMode;
  extractionFps?: number;
  matchingMode?: ReconstructionMatchingMode | "Not Started";
  matchingModeUsed?: ReconstructionMatchingMode | "Not Started" | "Unknown / legacy sparse run";
  sparseOutputExists: boolean;
  sparsePointCloudAvailable?: boolean;
  densePointCloudAvailable?: boolean;
  pointCount?: number;
  sparsePointCount?: number;
  densePointCount?: number;
  exportPathStatus?: string;
  viewerModeRecommendation?: ViewerModeRecommendation;
  currentBestViewerMode?: ViewerModeRecommendation;
  sparseModelFolders: string[];
  logFiles?: string[];
  logPreviews?: Record<string, string>;
  logPreviewSummary?: {
    featureExtraction?: string;
    matcher?: string;
    mapper?: string;
  };
  denseLogFiles?: string[];
  denseLogPreviewSummary?: {
    imageUndistorter?: string;
    patchMatchStereo?: string;
    stereoFusion?: string;
  };
  denseEndpointAvailable?: boolean;
  detectedSparseModelPath?: string | null;
  sparseModelPathExists?: boolean;
  denseWorkspacePath?: string;
  denseLastError?: string | null;
  warnings: string[];
  errorMessage: string | null;
  denseWarnings?: string[];
  denseErrorMessage?: string | null;
  likelyCauses?: string[];
  denseLikelyCauses?: string[];
  recommendedFixes?: string[];
  recommendedNextAction?: string;
  nextStep: string;
};

export type ViewerModeRecommendation = "dense_point_cloud" | "sparse_point_cloud" | "prototype_preview";

export type PointCloudPoint = {
  id?: number;
  x: number;
  y: number;
  z: number;
  r: number;
  g: number;
  b: number;
  error?: number;
};

export type PointCloudResponse = {
  available: boolean;
  source: "colmap_sparse" | "colmap_dense";
  pointCount: number;
  originalPointCount: number;
  returnedPointCount: number;
  points: PointCloudPoint[];
  message: string;
};
