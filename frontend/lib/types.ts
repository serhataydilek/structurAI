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
  reportCacheStatus?: "hit" | "miss";
  warnings?: string[];
  annotations: Annotation[];
  modelArtifactSummary?: ModelArtifactSummary;
  comparisonReadiness?: boolean;
  limitations: string[];
};

export type ModelArtifact = {
  artifactId: string; projectId: string; artifactType: "dense_point_cloud" | "textured_mesh" | "mesh" | "gaussian_splat" | "unknown";
  sourceTool: string; fileName: string; fileSize: number; storagePath: string; relativePath: string; notes: string; role?: "current_state" | "finished_reference" | "baseline" | "comparison_result" | null;
  stats: { vertexCount?: number; faceCount?: number | null; hasColor?: boolean; gaussianSplatDetected?: boolean; boundingBox?: { min: { x: number; y: number; z: number }; max: { x: number; y: number; z: number } } | null; statsPartial?: boolean };
  importWarning?: string;
  bundle?: { originalZipPath?: string; bundleRootPath?: string; mainObjPath?: string; mtlPath?: string | null; textureFiles?: string[]; textureCount?: number; mtlFound?: boolean };
  createdAt: string; updatedAt: string;
};
export type ModelArtifactSummary = { artifacts: ModelArtifact[]; measurementArtifactCount: number; latestDensePointCloud: ModelArtifact | null; latestMesh: ModelArtifact | null; latestReferenceModel: ModelArtifact | null; latestCurrentStateModel: ModelArtifact | null; comparisonReady: boolean; comparisonCount: number; latestComparison: { comparisonId: string; status: string } | null; message: string };
export type ArtifactComparison = { comparisonId: string; projectId: string; referenceArtifactId: string; currentArtifactId: string; status: string; notes: string; createdAt: string; updatedAt: string; referenceArtifact: ModelArtifact; currentArtifact: ModelArtifact; comparable: boolean; warning?: string | null; recommendation: string; analysisStatus?: string; warnings?: string[]; roughBoundsDelta?: { referenceSize?: Record<string,number>; currentSize?: Record<string,number>; scaleRatios?: number[] } | null; scaleMismatchWarning?: string | null; noProgressPercentageReason?: string | null };
export type RealityScanDiagnostics = { realityScanAvailable: boolean; resolvedRealityScanExe: string | null; source: string; versionHelpOutput?: string | null; supportsHeadless: boolean | "unknown"; supportsCommandFile: boolean | "unknown"; outputWriteable: boolean; errors: string[] };
export type PhotogrammetryJob = { jobId: string; projectId: string; engine: string; status: string; inputImageFolder: string; outputFolder: string; commandFilePath?: string | null; logPath?: string | null; logTail: string; notes: string; errors: string[]; imageCount?: number; ready?: boolean; manualRequired?: boolean };

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
export type FrameSelectionMode = "Balanced subset" | "All frames" | "Sharpest subset" | "Evenly spaced subset";
export type PreviewMode = "auto" | "interior" | "exterior";
export type VisualPreviewStatus = "not_started" | "preparing" | "ready" | "failed";
export type VisualPreviewType = "gaussian_splat_placeholder" | "external_viewer" | "future_visual_preview";
export type VisualPreviewTrainingStatus = "not_started" | "queued" | "running" | "complete" | "failed";
export type VisualPreviewExportStatus = "not_started" | "running" | "complete" | "failed";
export type VisualPreviewPreset = "smoke" | "quick" | "demo" | "quality";
export type ViewerTransform = {
  rotationX: number;
  rotationY: number;
  rotationZ: number;
  flipX: boolean;
  flipY: boolean;
  flipZ: boolean;
  scale: number;
  offsetX: number;
  offsetY: number;
  offsetZ: number;
};

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
  extractedFrameCount?: number;
  registeredImageCount?: number;
  registrationRatio?: number;
  registrationRatioLabel?: string;
  selectedRegistrationRatio?: number;
  sourceRegistrationRatio?: number;
  sourceRegistrationRatioLabel?: string;
  sparseQualityLabel?: string;
  sparseReconstructionQuality?: string;
  sourceFrameCount?: number;
  selectedFrameCount?: number;
  frameSelectionMode?: FrameSelectionMode | string;
  selectedFrameFolder?: string | null;
  reconstructionAttempts?: ReconstructionAttempt[];
  successfulAttempts?: ReconstructionAttempt[];
  failedOrEmptyAttempts?: ReconstructionAttempt[];
  hiddenFailedAttemptCount?: number;
  bestAttempt?: ReconstructionAttempt | null;
  latestAttempt?: ReconstructionAttempt | null;
  displayedAttempt?: ReconstructionAttempt | null;
  displayedAttemptRole?: "Best attempt" | "Latest attempt";
  denseReadiness?: {
    ready: boolean;
    recommended: boolean;
    reasons: string[];
  };
  visualPreviewStatus?: VisualPreviewStatus;
  visualPreviewReadiness?: VisualPreviewReadiness;
  visualPreview?: VisualPreviewOutput | null;
  visualPreviewReportStatus?: string;
  visualPreviewReportNote?: string;
  denseRecommended?: boolean;
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
  sceneAnalysis?: SceneAnalysis | null;
  viewerOrientationAlignedManually?: boolean;
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
  lowRegistrationRecommendations?: string[];
  recommendedFixes?: string[];
  recommendedNextAction?: string;
  nextStep: string;
};

export type VisualPreviewReadiness = {
  ready: boolean;
  recommended: boolean;
  label: string;
  reasons: string[];
  checks: Array<{
    key: string;
    label: string;
    passed: boolean;
    detail: string;
  }>;
  registeredImageCount: number;
  sparsePointCount: number;
  sparseQualityLabel: string;
  imageFolderPath?: string | null;
  colmapModelPath?: string | null;
};

export type VisualPreviewOutput = {
  visualPreviewId: string;
  projectId: string;
  attemptId: string;
  status: VisualPreviewStatus;
  previewType: VisualPreviewType;
  sourceAttemptId: string;
  createdAt: string;
  updatedAt: string;
  outputPath?: string | null;
  manifestPath?: string | null;
  trainingStatus: VisualPreviewTrainingStatus;
  exportStatus: VisualPreviewExportStatus;
  trainingStartedAt?: string | null;
  trainingFinishedAt?: string | null;
  trainingLogPath?: string | null;
  exportLogPath?: string | null;
  nerfstudioConfigPath?: string | null;
  splatOutputPath?: string | null;
  splatOutputSizeBytes?: number | null;
  viewerAssetPath?: string | null;
  errorMessage?: string | null;
  trainingPreset?: VisualPreviewPreset | string | null;
  maxIterations?: number | null;
  summaryJson: Record<string, unknown>;
};

export type VisualPreviewSummary = {
  projectId: string;
  status: VisualPreviewStatus;
  visualPreview?: VisualPreviewOutput | null;
  readiness: VisualPreviewReadiness;
  sourceAttempt?: ReconstructionAttempt | null;
  nextStep: string;
  limitations: string[];
};

export type VisualPreviewDiagnostics = {
  nerfstudioAvailable: boolean;
  nerfstudioPython?: string | null;
  nsTrainPath?: string | null;
  nsTrainFound?: boolean;
  nsExportPath?: string | null;
  nsExportFound?: boolean;
  cudaLikelyAvailable: boolean | "unknown";
  cudaAvailable?: boolean | "unknown";
  torchCudaVersion?: string | null;
  cudaDeviceName?: string | null;
  outputDirectoryWritable: boolean;
  warnings: string[];
  errors?: string[];
  recommendedSetupMessage: string;
};

export type VisualPreviewTrainingStatusResponse = {
  projectId: string;
  visualPreviewId?: string | null;
  status: VisualPreviewStatus;
  trainingStatus: VisualPreviewTrainingStatus;
  exportStatus: VisualPreviewExportStatus;
  trainingStartedAt?: string | null;
  trainingFinishedAt?: string | null;
  trainingLogPath?: string | null;
  exportLogPath?: string | null;
  recentTrainingLog: string;
  recentExportLog: string;
  nerfstudioConfigPath?: string | null;
  splatOutputPath?: string | null;
  splatOutputSizeBytes?: number | null;
  viewerAssetPath?: string | null;
  errorMessage?: string | null;
  trainingPreset?: VisualPreviewPreset | string | null;
  maxIterations?: number | null;
  summaryJson: Record<string, unknown>;
};

export type VisualPreviewSplatMetadata = {
  projectId: string;
  visualPreviewId?: string | null;
  exists: boolean;
  fileName?: string | null;
  fileSizeBytes?: number | null;
  createdAt?: string | null;
  modifiedAt?: string | null;
  relativePath?: string | null;
  downloadUrl?: string | null;
};

export type ReconstructionAttempt = {
  attemptId: string;
  projectId: string;
  createdAt: string;
  extractedFrameCount: number;
  sourceFrameCount?: number;
  selectedFrameCount?: number;
  frameSelectionMode?: FrameSelectionMode | string;
  selectedFrameFolder?: string | null;
  registeredImageCount: number;
  registrationRatio: number;
  registrationRatioLabel?: string;
  selectedRegistrationRatio?: number;
  sourceRegistrationRatio?: number;
  sourceRegistrationRatioLabel?: string;
  sparsePointCount: number;
  sparseQualityLabel: string;
  matchingMode: string;
  selectedFps: string;
  extractionFps: number;
  status: string;
  outputPath?: string | null;
  sceneAnalysisSummary?: Record<string, unknown>;
  viewerTransform?: Partial<ViewerTransform>;
  viewerPreviewMode?: PreviewMode;
  isBestAttempt: boolean;
  failureReason?: string | null;
  attemptDisplayStatus?: "Complete" | "Failed" | "No points";
  label?: string;
  source?: string;
};

export type SparseSweepAttempt = {
  attemptId?: string | null;
  frameSelectionMode?: string | null;
  matchingMode?: string | null;
  selectedFrameCount: number;
  registeredImageCount: number;
  selectedRegistrationRatio: number;
  registrationRatioLabel?: string;
  sparsePointCount: number;
  sparseQualityLabel: string;
  status: string;
  score: number;
  isBestAttempt: boolean;
  error?: string | null;
};

export type SparseSweepResponse = {
  projectId: string;
  status: string;
  attempts: SparseSweepAttempt[];
  bestAttempt?: ReconstructionAttempt | null;
  summary: ReconstructionSummary;
};

export type FrameSelectionPreview = {
  projectId: string;
  mode: FrameSelectionMode;
  sourceFrameCount: number;
  selectedFrameCount: number;
  cap: number;
  minimumWhenAvailable: number;
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
  attemptId?: string;
  attemptLabel?: string;
  isBestAttempt?: boolean;
  pointCount: number;
  originalPointCount: number;
  returnedPointCount: number;
  points: PointCloudPoint[];
  message: string;
};

export type SceneVector = {
  x: number;
  y: number;
  z: number;
};

export type SceneAnalysis = {
  available: boolean;
  pointCount: number;
  boundingBox: null | {
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
    minZ: number;
    maxZ: number;
    robustMinX: number;
    robustMaxX: number;
    robustMinY: number;
    robustMaxY: number;
    robustMinZ: number;
    robustMaxZ: number;
  };
  center: SceneVector | null;
  scale: number;
  suggestedCameraTarget?: SceneVector;
  suggestedCameraDistance?: number;
  floorEstimate: null | {
    axis: "y";
    level: number;
    method: string;
  };
  roomScaffold: null | {
    width: number;
    depth: number;
    height: number;
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
    minZ: number;
    maxZ: number;
  };
  cameraPath: {
    available: boolean;
    positions: Array<SceneVector & { imageId: number; imageName: string }>;
    message: string;
  };
  confidence: "Low" | "Medium" | "High";
  warnings: string[];
  message: string;
};
