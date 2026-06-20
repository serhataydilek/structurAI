"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/StatusBadge";
import { PointCloudColorMode, PointCloudPointSize, ViewerScene } from "@/components/ViewerScene";
import { API_BASE, addAnnotation, getCaptureSummary, getDensePointCloud, getDiagnostics, getFrames, getPointCloud, getProject, getReconstructionSummary, getSceneAnalysis, getVisualPreviewSummary, getVisualPreviewTrainingStatus, listAnnotations, prepareVisualPreview, runDenseReconstruction, runSparseReconstruction, runSparseReconstructionSweep, saveAttemptViewerTransform, trainVisualPreview } from "@/lib/api";
import type { Annotation, CaptureSummary, Diagnostics, FramePreview, PointCloudResponse, PreviewMode, Project, ReconstructionSummary, SceneAnalysis, SparseSweepAttempt, ViewerTransform, VisualPreviewSummary, VisualPreviewTrainingStatusResponse } from "@/lib/types";
import { AlertTriangle, Cpu, FileText, Loader2, Plus } from "lucide-react";

const identityViewerTransform: ViewerTransform = {
  rotationX: 0,
  rotationY: 0,
  rotationZ: 0,
  flipX: false,
  flipY: false,
  flipZ: false,
  scale: 1,
  offsetX: 0,
  offsetY: 0,
  offsetZ: 0
};

const SHOW_LEGACY_VISUAL_PREVIEW = false;

function normalizeViewerTransform(transform?: Partial<ViewerTransform>): ViewerTransform {
  return { ...identityViewerTransform, ...(transform ?? {}) };
}

export default function ViewerPage() {
  const params = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [summary, setSummary] = useState<CaptureSummary | null>(null);
  const [frames, setFrames] = useState<FramePreview[]>([]);
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null);
  const [reconstruction, setReconstruction] = useState<ReconstructionSummary | null>(null);
  const [pointCloud, setPointCloud] = useState<PointCloudResponse | null>(null);
  const [sparsePointCloud, setSparsePointCloud] = useState<PointCloudResponse | null>(null);
  const [densePointCloud, setDensePointCloud] = useState<PointCloudResponse | null>(null);
  const [visualPreview, setVisualPreview] = useState<VisualPreviewSummary | null>(null);
  const [visualTraining, setVisualTraining] = useState<VisualPreviewTrainingStatusResponse | null>(null);
  const [sceneAnalysis, setSceneAnalysis] = useState<SceneAnalysis | null>(null);
  const [reconstructing, setReconstructing] = useState(false);
  const [sweeping, setSweeping] = useState(false);
  const [sweepResults, setSweepResults] = useState<SparseSweepAttempt[]>([]);
  const [denseReconstructing, setDenseReconstructing] = useState(false);
  const [visualPreparing, setVisualPreparing] = useState(false);
  const [reconstructionError, setReconstructionError] = useState("");
  const [denseReconstructionError, setDenseReconstructionError] = useState("");
  const [visualPreviewError, setVisualPreviewError] = useState("");
  const [viewerMode, setViewerMode] = useState<"auto" | "dense" | "sparse">("auto");
  const [outputSelection, setOutputSelection] = useState<"sparse" | "visual" | "dense">("sparse");
  const [pointSize, setPointSize] = useState<PointCloudPointSize>("Medium");
  const [pointSizeValue, setPointSizeValue] = useState(0.045);
  const [pointOpacity, setPointOpacity] = useState(1);
  const [colorMode, setColorMode] = useState<PointCloudColorMode>("rgb");
  const [scanPreviewMode, setScanPreviewMode] = useState<PreviewMode>("auto");
  const [viewerTransform, setViewerTransform] = useState<ViewerTransform>(identityViewerTransform);
  const [savingViewerTransform, setSavingViewerTransform] = useState(false);
  const [showSparsePoints, setShowSparsePoints] = useState(true);
  const [showRoomBounds, setShowRoomBounds] = useState(true);
  const [showEstimatedFloor, setShowEstimatedFloor] = useState(true);
  const [showCameraPath, setShowCameraPath] = useState(true);
  const [showBoundingBox, setShowBoundingBox] = useState(false);
  const [showReference, setShowReference] = useState(true);
  const [presentationMode, setPresentationMode] = useState(false);
  const [debugCameraPath, setDebugCameraPath] = useState(false);
  const [showCameraSpheres, setShowCameraSpheres] = useState(true);
  const [cameraPathPointSize, setCameraPathPointSize] = useState(0.04);
  const [cameraPathPointOpacity, setCameraPathPointOpacity] = useState(0.6);
  const [cameraPathLineOpacity, setCameraPathLineOpacity] = useState(0.45);
  const [viewerResetKey, setViewerResetKey] = useState(0);
  const [note, setNote] = useState("");
  const [selectedAttemptId, setSelectedAttemptId] = useState<string>("");

  useEffect(() => {
    getProject(params.id).then(setProject).catch(() => setProject(null));
    listAnnotations(params.id).then(setAnnotations).catch(() => setAnnotations([]));
    getCaptureSummary(params.id).then(setSummary).catch(() => setSummary(null));
    getFrames(params.id).then(setFrames).catch(() => setFrames([]));
    getDiagnostics().then(setDiagnostics).catch(() => setDiagnostics(null));
    getVisualPreviewSummary(params.id).then(setVisualPreview).catch(() => setVisualPreview(null));
    getVisualPreviewTrainingStatus(params.id).then(setVisualTraining).catch(() => setVisualTraining(null));
    refreshReconstruction();
  }, [params.id]);

  useEffect(() => {
    if (visualTraining?.trainingStatus !== "queued" && visualTraining?.trainingStatus !== "running" && visualTraining?.exportStatus !== "running") return;
    const timer = window.setTimeout(() => {
      getVisualPreviewTrainingStatus(params.id).then(setVisualTraining).catch(() => undefined);
      getVisualPreviewSummary(params.id).then(setVisualPreview).catch(() => undefined);
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [params.id, visualTraining?.trainingStatus, visualTraining?.exportStatus, visualTraining?.recentTrainingLog]);

  async function refreshReconstruction() {
    try {
      const next = await getReconstructionSummary(params.id);
      setReconstruction(next);
      let loadedDense: PointCloudResponse | null = null;
      let loadedSparse: PointCloudResponse | null = null;
      let loadedSceneAnalysis: SceneAnalysis | null = null;
      if (next.densePointCloudAvailable) {
        loadedDense = await getDensePointCloud(params.id).catch(() => null);
      }
      if (next.sparsePointCloudAvailable) {
        const attemptId = selectedAttemptId || next.bestAttempt?.attemptId || next.displayedAttempt?.attemptId;
        if (!selectedAttemptId && attemptId) setSelectedAttemptId(attemptId);
        loadedSparse = await getPointCloud(params.id, 50000, attemptId).catch(() => null);
        loadedSceneAnalysis = await getSceneAnalysis(params.id, attemptId).catch(() => null);
      }
      setDensePointCloud(loadedDense);
      setSparsePointCloud(loadedSparse);
      setSceneAnalysis(loadedSceneAnalysis);
      setPointCloud(loadedDense?.available ? loadedDense : loadedSparse?.available ? loadedSparse : null);
      return next;
    } catch {
      setReconstruction(null);
      setPointCloud(null);
      setSparsePointCloud(null);
      setDensePointCloud(null);
      setSceneAnalysis(null);
      return null;
    }
  }

  async function onSelectAttempt(attemptId: string) {
    setSelectedAttemptId(attemptId);
    const [nextPointCloud, nextSceneAnalysis] = await Promise.all([
      getPointCloud(params.id, 50000, attemptId).catch(() => null),
      getSceneAnalysis(params.id, attemptId).catch(() => null)
    ]);
    setSparsePointCloud(nextPointCloud);
    setSceneAnalysis(nextSceneAnalysis);
    setPointCloud(densePointCloud?.available && viewerMode === "dense" ? densePointCloud : nextPointCloud);
    setViewerResetKey((current) => current + 1);
  }

  async function onRunSparseReconstruction() {
    setReconstructing(true);
    setReconstructionError("");
    setPointCloud(null);
    setReconstruction((current) => current ? { ...current, status: "Reconstructing Sparse Model" } : current);
    try {
      const result = await runSparseReconstruction(params.id);
      setReconstruction(result);
      if (result.sparsePointCloudAvailable) {
        const nextPointCloud = await getPointCloud(params.id);
        setPointCloud(nextPointCloud);
      }
      await refreshReconstruction();
      getProject(params.id).then(setProject).catch(() => undefined);
    } catch (error) {
      setReconstructionError(error instanceof Error ? error.message : "Sparse reconstruction failed");
      await refreshReconstruction();
      getProject(params.id).then(setProject).catch(() => undefined);
    } finally {
      setReconstructing(false);
    }
  }

  async function onRunDenseReconstruction() {
    setDenseReconstructing(true);
    setDenseReconstructionError("");
    setReconstruction((current) => current ? { ...current, denseStatus: "Dense Reconstruction Running" } : current);
    try {
      await runDenseReconstruction(params.id);
      await refreshReconstruction();
      getProject(params.id).then(setProject).catch(() => undefined);
    } catch (error) {
      setDenseReconstructionError(error instanceof Error ? error.message : "Dense reconstruction failed");
      await refreshReconstruction();
      getProject(params.id).then(setProject).catch(() => undefined);
    } finally {
      setDenseReconstructing(false);
    }
  }

  async function onPrepareVisualPreview() {
    setVisualPreparing(true);
    setVisualPreviewError("");
    try {
      const next = await prepareVisualPreview(params.id);
      setVisualPreview(next);
      setOutputSelection("visual");
    } catch (error) {
      setVisualPreviewError(error instanceof Error ? error.message : "Visual preview preparation failed");
      getVisualPreviewSummary(params.id).then(setVisualPreview).catch(() => undefined);
    } finally {
      setVisualPreparing(false);
    }
  }

  async function onTrainVisualPreview() {
    setVisualPreparing(true);
    setVisualPreviewError("");
    try {
      const next = await trainVisualPreview(params.id, { visualPreviewId: visualPreview?.visualPreview?.visualPreviewId, preset: "quick" });
      setVisualTraining(next);
      getVisualPreviewSummary(params.id).then(setVisualPreview).catch(() => undefined);
      setOutputSelection("visual");
    } catch (error) {
      setVisualPreviewError(error instanceof Error ? error.message : "Visual preview training could not start");
      getVisualPreviewTrainingStatus(params.id).then(setVisualTraining).catch(() => undefined);
    } finally {
      setVisualPreparing(false);
    }
  }

  async function onRunSparseSweep() {
    setSweeping(true);
    setReconstructionError("");
    try {
      const result = await runSparseReconstructionSweep(params.id);
      setSweepResults(result.attempts);
      setReconstruction(result.summary);
      await refreshReconstruction();
      getProject(params.id).then(setProject).catch(() => undefined);
    } catch (error) {
      setReconstructionError(error instanceof Error ? error.message : "Sparse experiment sweep failed");
      await refreshReconstruction();
    } finally {
      setSweeping(false);
    }
  }

  async function submitNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!note.trim()) return;
    const created = await addAnnotation(params.id, note);
    setAnnotations((current) => [...current, created]);
    setNote("");
  }

  const inputFrameCount = reconstruction?.inputFrameCount ?? summary?.extractedFrameCount ?? 0;
  const sparseStatus = reconstruction?.sparseStatus ?? reconstruction?.status ?? "Not Started";
  const denseStatus = reconstruction?.denseStatus ?? "Dense Reconstruction Not Started";
  const sparseNotStarted = sparseStatus === "Not Started";
  const colmapAvailable = reconstruction?.colmapAvailable ?? diagnostics?.colmap.colmapAvailable ?? false;
  const denseLikelyAvailable = reconstruction?.denseReconstructionLikelyAvailable ?? diagnostics?.colmap.denseReconstructionLikelyAvailable ?? "unknown";
  const colmapCudaHint = reconstruction?.colmapCudaHint ?? diagnostics?.colmap.colmapCudaHint ?? (colmapAvailable ? "COLMAP detected; CUDA dense-stereo support is unknown." : "COLMAP not detected.");
  const denseLikelyUnavailable = denseLikelyAvailable === false;
  const attempts = reconstruction?.reconstructionAttempts ?? [];
  const successfulAttempts = reconstruction?.successfulAttempts ?? attempts.filter((attempt) => attempt.status === "Sparse Reconstruction Complete" && (attempt.registeredImageCount ?? 0) > 0 && (attempt.sparsePointCount ?? 0) > 0);
  const failedOrEmptyAttempts = reconstruction?.failedOrEmptyAttempts ?? attempts.filter((attempt) => !successfulAttempts.some((successful) => successful.attemptId === attempt.attemptId));
  const hasSparseAttempt = attempts.length > 0;
  const sparseFinished = sparseStatus === "Sparse Reconstruction Complete" || sparseStatus === "Sparse Reconstruction Failed";
  const sparseQualityLabel = reconstruction?.sparseQualityLabel ?? "Not evaluated";
  const sparseQualityPoor = Boolean(hasSparseAttempt && sparseFinished && sparseQualityLabel === "Poor Sparse Reconstruction" && ((reconstruction?.registeredImageCount ?? 0) < 15 || (reconstruction?.sparsePointCount ?? 0) < 1500));
  const showSparseAction = inputFrameCount > 0 && sparseNotStarted;
  const denseReadiness = reconstruction?.denseReadiness;
  const denseReady = denseReadiness?.ready ?? true;
  const canRunDense = sparseStatus === "Sparse Reconstruction Complete" && denseStatus !== "Dense Reconstruction Complete" && colmapAvailable && !denseLikelyUnavailable && denseReady && !sparseQualityPoor;
  const denseRecommendedPath = "Advanced / legacy diagnostics only. Use RealityScan for client-quality geometry.";
  const denseLogEntries = Object.entries(reconstruction?.denseLogPreviewSummary ?? {}).filter(([, value]) => value.trim().length > 0);
  const visualReadiness = visualPreview?.readiness;
  const visualManifest = visualPreview?.visualPreview;
  const visualReady = visualReadiness?.ready ?? false;
  const visualStatus = visualPreview?.status ?? "not_started";
  const visualManifestReady = visualStatus === "ready" && Boolean(visualManifest);
  const visualTrainingStatus = visualTraining?.trainingStatus ?? visualManifest?.trainingStatus ?? "not_started";
  const visualExportStatus = visualTraining?.exportStatus ?? visualManifest?.exportStatus ?? "not_started";
  const selectedPointCloud = viewerMode === "dense"
    ? densePointCloud
    : viewerMode === "sparse"
      ? sparsePointCloud
      : densePointCloud?.available
        ? densePointCloud
        : sparsePointCloud;
  const hasDensePointCloud = Boolean(densePointCloud?.available && densePointCloud.points.length > 0);
  const hasSparsePointCloud = Boolean(sparsePointCloud?.available && sparsePointCloud.points.length > 0);
  const activePointCloud = selectedPointCloud?.available ? selectedPointCloud : pointCloud;
  const sparseSceneAvailable = Boolean(sceneAnalysis?.available && activePointCloud?.source === "colmap_sparse");
  const activeSceneAnalysis = activePointCloud?.source === "colmap_sparse" ? sceneAnalysis : null;
  const autoPreviewMode: Exclude<PreviewMode, "auto"> = project?.scan_type === "Building Scan" || ((summary?.imageCount ?? 0) >= 40 && (summary?.videoCount ?? 0) === 0) ? "exterior" : "interior";
  const activePreviewMode: Exclude<PreviewMode, "auto"> = scanPreviewMode === "auto" ? autoPreviewMode : scanPreviewMode;
  const outputType = activePointCloud?.source === "colmap_dense"
    ? "Advanced dense diagnostic preview"
    : activePointCloud?.source === "colmap_sparse" && activePreviewMode === "exterior"
      ? "Sparse validation preview"
      : sparseSceneAvailable
        ? "Sparse validation preview"
        : activePointCloud?.source === "colmap_sparse"
          ? "Sparse validation point cloud"
          : "No validation output";
  const hasPointCloud = Boolean(activePointCloud?.available && activePointCloud.points.length > 0);
  const title = activePointCloud?.source === "colmap_dense" ? "Advanced Dense Diagnostic Preview" : activePreviewMode === "exterior" && hasPointCloud ? "Sparse Validation Preview" : sparseSceneAvailable ? "Sparse Validation Preview" : hasPointCloud ? "Sparse Validation Point Cloud" : "No Validation Output Yet";
  const explanation = activePointCloud?.source === "colmap_dense"
    ? "This is a legacy COLMAP dense diagnostic. It is not the primary client-quality model workflow."
    : activePreviewMode === "exterior" && hasPointCloud
      ? "This is a real COLMAP sparse validation point cloud. Scale and orientation are arbitrary until aligned with the viewer controls."
      : sparseSceneAvailable
      ? "This view uses optional COLMAP sparse validation plus estimated room bounds to make capture coverage easier to inspect. It is not a final model."
      : hasPointCloud
        ? "This is a real sparse validation point cloud from the uploaded capture. It is not the final model."
    : "Upload media, process capture, then prepare a RealityScan job. Sparse validation is optional.";
  const registeredImageCount = reconstruction?.registeredImageCount ?? 0;
  const registrationRatioLabel = reconstruction?.registrationRatioLabel ?? "0%";
  const selectedFrameCount = reconstruction?.selectedFrameCount ?? reconstruction?.extractedFrameCount ?? inputFrameCount;
  const selectedRegistrationPercent = Math.round((reconstruction?.selectedRegistrationRatio ?? reconstruction?.registrationRatio ?? 0) * 100);
  const selectedAttempt = attempts.find((attempt) => attempt.attemptId === selectedAttemptId) ?? reconstruction?.displayedAttempt ?? reconstruction?.bestAttempt;
  const bestAttempt = reconstruction?.bestAttempt;
  const latestAttempt = reconstruction?.latestAttempt;
  const latestWorseThanBest = Boolean(bestAttempt && latestAttempt && bestAttempt.attemptId !== latestAttempt.attemptId);
  const selectedFramePreviews = frames.length > 0
    ? [frames[0], frames[Math.floor(frames.length / 2)], frames[frames.length - 1]].filter((frame, index, all) => frame && all.findIndex((item) => item.filename === frame.filename) === index)
    : [];
  const photoSetRecommendations = [
    "Take 40-80 sharp photos.",
    "Keep 60-70% overlap between photos.",
    "Keep the same objects visible across multiple photos.",
    "Capture corners, doors, windows, furniture, and textured objects.",
    "Avoid blank walls, mirrors, glass, and shiny surfaces.",
    "Use Photo Exhaustive matching for photo sets."
  ];
  const room = sceneAnalysis?.roomScaffold;
  const denseAvailabilityText = denseLikelyUnavailable
    ? "Legacy dense COLMAP likely requires a CUDA-enabled COLMAP build on this machine."
    : denseLikelyAvailable === true
      ? "Dense reconstruction support appears available."
      : "Dense reconstruction support is unknown on this machine.";

  useEffect(() => {
    if (!selectedAttempt) return;
    setViewerTransform(normalizeViewerTransform(selectedAttempt.viewerTransform));
    setScanPreviewMode(selectedAttempt.viewerPreviewMode ?? "auto");
  }, [selectedAttempt?.attemptId, selectedAttempt?.viewerPreviewMode, selectedAttempt?.viewerTransform]);

  useEffect(() => {
    if (activePreviewMode === "exterior") {
      setShowEstimatedFloor(false);
      setShowRoomBounds(false);
      setShowBoundingBox(true);
      setShowCameraPath(false);
      setShowReference(false);
      setDebugCameraPath(false);
      setShowCameraSpheres(false);
      setCameraPathPointSize(0.026);
      setCameraPathPointOpacity(0.35);
      setCameraPathLineOpacity(0.32);
      setPointSize("Medium");
      setPointSizeValue(0.052);
    } else {
      setShowEstimatedFloor(true);
      setShowRoomBounds(true);
      setShowBoundingBox(false);
      setShowCameraPath(true);
      setShowReference(true);
      setDebugCameraPath(true);
      setShowCameraSpheres(true);
      setCameraPathPointSize(0.045);
      setCameraPathPointOpacity(0.8);
      setCameraPathLineOpacity(0.75);
      setPointSize("Medium");
      setPointSizeValue(0.045);
    }
  }, [activePreviewMode]);

  function rotate(axis: "rotationX" | "rotationY" | "rotationZ", amount: number) {
    setViewerTransform((current) => ({ ...current, [axis]: (((current[axis] + amount) % 360) + 360) % 360 }));
    setViewerResetKey((current) => current + 1);
  }

  function flip(axis: "flipX" | "flipY" | "flipZ") {
    setViewerTransform((current) => ({ ...current, [axis]: !current[axis] }));
    setViewerResetKey((current) => current + 1);
  }

  function resetOrientation() {
    setViewerTransform(identityViewerTransform);
    setViewerResetKey((current) => current + 1);
  }

  function autoOrient() {
    const box = sceneAnalysis?.boundingBox;
    if (!box) {
      resetOrientation();
      return;
    }
    const spans = [
      { axis: "x", span: Math.abs(box.robustMaxX - box.robustMinX) },
      { axis: "y", span: Math.abs(box.robustMaxY - box.robustMinY) },
      { axis: "z", span: Math.abs(box.robustMaxZ - box.robustMinZ) }
    ].sort((a, b) => b.span - a.span);
    const thinnest = spans[2]?.axis;
    const next = { ...identityViewerTransform };
    if (thinnest === "x") next.rotationZ = 90;
    if (thinnest === "z") next.rotationX = 90;
    setViewerTransform(next);
    setViewerResetKey((current) => current + 1);
  }

  async function onSaveOrientation() {
    if (!selectedAttempt?.attemptId) return;
    setSavingViewerTransform(true);
    try {
      await saveAttemptViewerTransform(params.id, selectedAttempt.attemptId, viewerTransform, scanPreviewMode);
      await refreshReconstruction();
    } finally {
      setSavingViewerTransform(false);
    }
  }

  function attemptStatus(attempt: { status: string; registeredImageCount?: number; sparsePointCount?: number }) {
    if (attempt.status.includes("Failed")) return "Failed";
    if ((attempt.registeredImageCount ?? 0) <= 0 || (attempt.sparsePointCount ?? 0) <= 0) return "No points";
    return "Complete";
  }

  const renderCameraPath = activePreviewMode === "exterior" ? debugCameraPath && showCameraPath && !presentationMode : showCameraPath && !presentationMode;
  const renderReference = presentationMode ? false : showReference;
  const renderBoundingBox = presentationMode ? showBoundingBox : showBoundingBox;
  const selectedOutputDescription = outputSelection === "visual"
    ? "Legacy visual preview inputs are retained for experiment records only."
    : outputSelection === "dense"
      ? "Advanced dense diagnostics are not the primary Structura model workflow."
      : explanation;

  return (
    <AppShell>
      <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
        <section>
          <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm text-brand">Capture Validation Viewer</p>
              <h1 className="mt-2 text-3xl font-semibold text-white">{title}</h1>
              <p className="mt-2 text-sm text-slate-400">
                {selectedOutputDescription}
              </p>
            </div>
            <Link href={`/projects/${params.id}/report`} className="inline-flex items-center gap-2 rounded-md bg-brand px-4 py-2.5 font-semibold text-ink hover:bg-cyan-200">
              <FileText size={17} /> Export Report
            </Link>
          </div>
          <div className="glass-panel mb-5 rounded-lg p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">Outputs</p>
                <p className="mt-1 text-xs text-slate-400">Use the sparse viewer for capture validation; import client-quality geometry through Model Artifacts.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link href={`/projects/${params.id}/model-artifacts`} className="rounded-md border border-brand/40 px-3 py-2 text-sm font-medium text-brand hover:bg-brand/10">
                  Model Artifacts
                </Link>
              </div>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              {([
                {
                  key: "sparse",
                  title: "Sparse Validation Preview",
                  status: sparseStatus,
                  readiness: hasSparsePointCloud ? "Ready" : sparseNotStarted ? "Not prepared" : "Check reconstruction",
                  body: "Optional COLMAP point cloud for capture coverage and registration checks.",
                  limitation: "Validation output only; not the final RealityScan model."
                },
                {
                  key: "visual",
                  title: "Legacy visual preview",
                  status: visualManifestReady ? "Manifest ready" : visualStatus === "failed" ? "Failed" : "Not prepared",
                  readiness: visualExportStatus === "complete" ? "Export ready" : visualTrainingStatus === "running" || visualTrainingStatus === "queued" ? "Training running" : visualReadiness?.label ?? "Not evaluated",
                  body: "Retained for legacy experiment records only.",
                  limitation: "Not a measurement-grade model."
                },
                {
                  key: "dense",
                  title: "Advanced dense diagnostic",
                  status: denseStatus,
                  readiness: denseLikelyUnavailable ? "Not recommended with current COLMAP" : denseReady ? "Ready to try" : "Not ready",
                  body: "Legacy COLMAP diagnostic path.",
                  limitation: "Use RealityScan artifacts for client-quality geometry."
                }
              ] as const).filter((item) => SHOW_LEGACY_VISUAL_PREVIEW || item.key !== "visual").map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => {
                    setOutputSelection(item.key);
                    if (item.key === "sparse") setViewerMode("sparse");
                    if (item.key === "dense") setViewerMode("dense");
                  }}
                  className={`rounded-md border p-4 text-left transition ${outputSelection === item.key ? "border-brand bg-brand/10" : "border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"}`}
                >
                  <p className="text-sm font-semibold text-white">{item.title}</p>
                  <p className="mt-2 text-xs text-slate-500">Status</p>
                  <p className="mt-1 text-sm font-semibold text-slate-100">{item.status}</p>
                  <p className="mt-2 text-xs text-slate-500">Readiness</p>
                  <p className="mt-1 text-xs text-slate-300">{item.readiness}</p>
                  <p className="mt-3 text-xs leading-5 text-slate-400">{item.body}</p>
                  <p className="mt-2 text-xs leading-5 text-amber-100/85">{item.limitation}</p>
                </button>
              ))}
            </div>
          </div>
          <div className="glass-panel mb-5 rounded-lg p-5">
            <div className="grid gap-4 md:grid-cols-6">
              <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                <p className="text-xs text-slate-500">Extracted frames</p>
                <p className="mt-1 text-xl font-semibold text-white">{inputFrameCount}</p>
              </div>
              <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                <p className="text-xs text-slate-500">Registered images</p>
                <p className="mt-1 text-xl font-semibold text-white">{registeredImageCount}</p>
              </div>
              <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                <p className="text-xs text-slate-500">Registration ratio</p>
                <p className="mt-1 text-xl font-semibold text-white">{registrationRatioLabel}</p>
              </div>
              <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                <p className="text-xs text-slate-500">Sparse status</p>
                <p className="mt-1 text-sm font-semibold text-white">{sparseStatus}</p>
              </div>
              <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                <p className="text-xs text-slate-500">Dense status</p>
                <p className="mt-1 text-sm font-semibold text-white">{denseStatus}</p>
              </div>
              <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                <p className="text-xs text-slate-500">Sparse points</p>
                <p className="mt-1 text-xl font-semibold text-white">{reconstruction?.sparsePointCount ?? reconstruction?.pointCount ?? 0}</p>
              </div>
              <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                <p className="text-xs text-slate-500">Dense points</p>
                <p className="mt-1 text-xl font-semibold text-white">{reconstruction?.densePointCount ?? 0}</p>
              </div>
              <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                <p className="text-xs text-slate-500">Output type</p>
                <p className="mt-1 text-sm font-semibold text-white">{outputType}</p>
              </div>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-3">
              <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                <p className="text-xs text-slate-500">Sparse quality</p>
                <p className="mt-1 text-sm font-semibold text-white">{sparseQualityLabel}</p>
              </div>
              <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                <p className="text-xs text-slate-500">Dense availability</p>
                <p className="mt-1 text-sm font-semibold text-white">{denseLikelyUnavailable ? "Unavailable with current COLMAP" : denseReady ? "Available to try" : "Not ready"}</p>
              </div>
              <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                <p className="text-xs text-slate-500">Current output</p>
                <p className="mt-1 text-sm font-semibold text-white">{outputType}</p>
              </div>
            </div>
            <div className="mt-4 rounded-md border border-white/10 bg-white/[0.03] p-3 text-sm text-slate-300">
              Next action: {reconstruction?.recommendedNextAction ?? "Prepare RealityScan Job"}
            </div>
            {sparseQualityPoor && (
              <div className="mt-4 rounded-lg border border-red-400/30 bg-red-400/10 p-5 text-red-50">
                <p className="text-base font-semibold">
                  COLMAP could only register {registeredImageCount} out of {selectedFrameCount} selected frames. The reconstruction is too weak to produce a readable scene.
                </p>
                <div className="mt-4 grid gap-3 md:grid-cols-4">
                  <div>
                    <p className="text-xs text-red-100/70">Selected frames</p>
                    <p className="text-lg font-semibold">{selectedFrameCount}</p>
                  </div>
                  <div>
                    <p className="text-xs text-red-100/70">Registered images</p>
                    <p className="text-lg font-semibold">{registeredImageCount}</p>
                  </div>
                  <div>
                    <p className="text-xs text-red-100/70">Selected registration ratio</p>
                    <p className="text-lg font-semibold">{selectedRegistrationPercent}%</p>
                  </div>
                  <div>
                    <p className="text-xs text-red-100/70">Sparse points</p>
                    <p className="text-lg font-semibold">{reconstruction?.sparsePointCount ?? 0}</p>
                  </div>
                </div>
                <p className="mt-3 text-sm text-red-100/85">Likely reason: Most frames could not be reliably matched.</p>
                <div className="mt-4 flex flex-wrap gap-3">
                  <Link href={`/projects/${params.id}/upload`} className="rounded-md bg-red-100 px-4 py-2.5 text-sm font-semibold text-red-950 hover:bg-white">
                    Try a better capture
                  </Link>
                  <button
                    type="button"
                    disabled={!colmapAvailable || reconstructing || sweeping}
                    onClick={onRunSparseSweep}
                    className="rounded-md border border-red-100/30 px-4 py-2.5 text-sm font-semibold text-red-50 hover:bg-red-100/10 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {sweeping ? "Running Sparse Experiment Sweep..." : "Run another sparse sweep"}
                  </button>
                </div>
              </div>
            )}
            {sparseQualityPoor && (
              <div className="mt-4 rounded-lg border border-emerald-300/20 bg-emerald-300/10 p-5">
                <p className="text-base font-semibold text-emerald-100">Video capture is failing. Try a sharp photo set instead.</p>
                <ul className="mt-3 grid gap-2 text-sm text-emerald-50/90 md:grid-cols-2">
                  {photoSetRecommendations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {attempts.length > 0 && (
              <div className="mt-4 rounded-md border border-white/10 bg-slate-950/60 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">Reconstruction Attempt</p>
                    <p className="mt-1 text-xs text-slate-400">
                      Current displayed attempt: {selectedAttempt?.isBestAttempt ? "Best attempt" : latestAttempt?.attemptId === selectedAttempt?.attemptId ? "Latest attempt" : "Selected attempt"}
                    </p>
                  </div>
                  <select
                    value={selectedAttemptId || selectedAttempt?.attemptId || ""}
                    onChange={(event) => onSelectAttempt(event.target.value)}
                    className="rounded-md border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-brand"
                  >
                    {attempts.map((attempt) => (
                      <option key={attempt.attemptId} value={attempt.attemptId}>
                        {`${attempt.isBestAttempt ? "Best attempt - " : ""}${latestAttempt?.attemptId === attempt.attemptId ? "Latest attempt - " : ""}${attemptStatus(attempt)} - ${attempt.label ?? `${attempt.sparseQualityLabel} - ${attempt.registeredImageCount}/${attempt.extractedFrameCount} registered - ${attempt.sparsePointCount} points`}`}
                      </option>
                    ))}
                  </select>
                </div>
                {successfulAttempts.length > 0 && (
                  <p className="mt-3 text-xs text-slate-400">
                    Showing {successfulAttempts.length} successful attempt{successfulAttempts.length === 1 ? "" : "s"} first. {failedOrEmptyAttempts.length > 0 ? `${failedOrEmptyAttempts.length} failed/empty attempt${failedOrEmptyAttempts.length === 1 ? "" : "s"} kept for debugging.` : ""}
                  </p>
                )}
                {latestWorseThanBest && (
                  <div className="mt-3 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">
                    Latest attempt is worse than the best saved attempt. Viewer is showing the best attempt by default.
                  </div>
                )}
                {selectedAttempt && (
                  <div className="mt-4 grid gap-3 md:grid-cols-5">
                    <div>
                      <p className="text-xs text-slate-500">Frame selection</p>
                      <p className="mt-1 text-sm font-semibold text-white">{selectedAttempt.frameSelectionMode ?? "All frames"}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Selected frames</p>
                      <p className="mt-1 text-sm font-semibold text-white">{selectedAttempt.selectedFrameCount ?? selectedAttempt.extractedFrameCount}/{selectedAttempt.sourceFrameCount ?? selectedAttempt.extractedFrameCount}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Registered</p>
                      <p className="mt-1 text-sm font-semibold text-white">{selectedAttempt.registeredImageCount}/{selectedAttempt.selectedFrameCount ?? selectedAttempt.extractedFrameCount}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Ratio</p>
                      <p className="mt-1 text-sm font-semibold text-white">{selectedAttempt.registrationRatioLabel ?? `${Math.round(selectedAttempt.registrationRatio * 100)}%`}</p>
                      <p className="mt-1 text-xs text-slate-500">{selectedAttempt.sourceFrameCount ?? selectedAttempt.extractedFrameCount} source frames</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Quality</p>
                      <p className="mt-1 text-sm font-semibold text-white">{selectedAttempt.sparseQualityLabel}</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {selectedAttempt.isBestAttempt && <span className="rounded border border-emerald-300/30 px-2 py-0.5 text-xs text-emerald-100">Best attempt</span>}
                        {latestAttempt?.attemptId === selectedAttempt.attemptId && <span className="rounded border border-slate-400/30 px-2 py-0.5 text-xs text-slate-200">Latest attempt</span>}
                        <span className="rounded border border-white/10 px-2 py-0.5 text-xs text-slate-300">{attemptStatus(selectedAttempt)}</span>
                      </div>
                    </div>
                  </div>
                )}
                {failedOrEmptyAttempts.length > 0 && (
                  <details className="mt-4 rounded-md border border-white/10 bg-white/[0.03] p-3">
                    <summary className="cursor-pointer text-xs font-semibold text-slate-300">Failed or empty attempts</summary>
                    <div className="mt-3 space-y-2 text-xs text-slate-400">
                      {failedOrEmptyAttempts.map((attempt) => (
                        <div key={attempt.attemptId} className="rounded border border-white/10 bg-slate-950/60 p-2">
                          <span className="font-semibold text-slate-200">{attemptStatus(attempt)}</span> - {attempt.frameSelectionMode ?? "All frames"} / {attempt.matchingMode}: {attempt.registeredImageCount}/{attempt.selectedFrameCount ?? attempt.extractedFrameCount} registered, {attempt.sparsePointCount} points
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            )}
            <div className="mt-4 rounded-md border border-amber-300/20 bg-amber-300/10 p-4 text-sm text-amber-100">
              This will run multiple COLMAP sparse attempts with different frame selection strategies. It may take several minutes but can improve reconstruction quality.
              <button
                type="button"
                disabled={!colmapAvailable || reconstructing || sweeping}
                onClick={onRunSparseSweep}
                className="mt-3 rounded-md border border-amber-300/30 px-3 py-2 text-sm font-semibold text-amber-100 hover:bg-amber-300/10 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {sweeping ? "Running Sparse Experiment Sweep..." : "Run Sparse Experiment Sweep"}
              </button>
            </div>
            {sweepResults.length > 0 && (
              <div className="mt-4 overflow-hidden rounded-md border border-white/10">
                <table className="w-full text-left text-sm">
                  <thead className="bg-white/[0.04] text-xs text-slate-400">
                    <tr>
                      <th className="px-3 py-2">Mode</th>
                      <th className="px-3 py-2">Matching</th>
                      <th className="px-3 py-2">Selected</th>
                      <th className="px-3 py-2">Registered</th>
                      <th className="px-3 py-2">Ratio</th>
                      <th className="px-3 py-2">Points</th>
                      <th className="px-3 py-2">Quality</th>
                      <th className="px-3 py-2">Best</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10">
                    {sweepResults.map((attempt, index) => (
                      <tr key={attempt.attemptId ?? index} className="text-slate-200">
                        <td className="px-3 py-2">{attempt.frameSelectionMode}</td>
                        <td className="px-3 py-2">{attempt.matchingMode}</td>
                        <td className="px-3 py-2">{attempt.selectedFrameCount}</td>
                        <td className="px-3 py-2">{attempt.registeredImageCount}</td>
                        <td className="px-3 py-2">{attempt.registrationRatioLabel ?? `${Math.round(attempt.selectedRegistrationRatio * 100)}%`}</td>
                        <td className="px-3 py-2">{attempt.sparsePointCount}</td>
                        <td className="px-3 py-2">{attempt.sparseQualityLabel}</td>
                        <td className="px-3 py-2">{attempt.isBestAttempt ? "Yes" : "No"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {sparseSceneAvailable && (
              <div className="mt-4 rounded-md border border-white/10 bg-slate-950/60 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">{activePreviewMode === "exterior" ? "Sparse Building Stats" : "Sparse Scene Stats"}</p>
                    <p className="mt-1 text-xs text-slate-400">
                      {activePreviewMode === "exterior"
                        ? "The preview shows COLMAP sparse points, camera poses, and an orientation-aware bounding box."
                        : "The preview combines sparse COLMAP points with estimated room bounds."}
                    </p>
                  </div>
                  <span className="rounded-md border border-brand/25 bg-brand/10 px-2.5 py-1 text-xs font-semibold text-cyan-100">
                    {sceneAnalysis?.confidence ?? "Low"} confidence
                  </span>
                </div>
                <div className="mt-4 grid gap-3 md:grid-cols-5">
                  <div>
                    <p className="text-xs text-slate-500">Sparse points</p>
                    <p className="mt-1 text-sm font-semibold text-white">{sceneAnalysis?.pointCount ?? reconstruction?.sparsePointCount ?? 0}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">{activePreviewMode === "exterior" ? "Bounds X" : "Width"}</p>
                    <p className="mt-1 text-sm font-semibold text-white">{room ? room.width.toFixed(2) : "-"} units</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">{activePreviewMode === "exterior" ? "Bounds Z" : "Depth"}</p>
                    <p className="mt-1 text-sm font-semibold text-white">{room ? room.depth.toFixed(2) : "-"} units</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">{activePreviewMode === "exterior" ? "Bounds Y" : "Height"}</p>
                    <p className="mt-1 text-sm font-semibold text-white">{room ? room.height.toFixed(2) : "-"} units</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Camera path</p>
                    <p className="mt-1 text-sm font-semibold text-white">{sceneAnalysis?.cameraPath.available ? `${sceneAnalysis.cameraPath.positions.length} poses` : "Unavailable"}</p>
                  </div>
                </div>
                <div className="mt-3 rounded-md border border-white/10 bg-white/[0.03] p-3 text-xs text-slate-300">
                  {denseAvailabilityText} Recommended path: prepare a RealityScan job and import the exported model artifact.
                </div>
              </div>
            )}
            <div className="mt-4 rounded-md border border-white/10 bg-slate-950/60 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">Legacy dense readiness</p>
                  <p className="mt-1 text-xs text-slate-400">{colmapCudaHint}</p>
                </div>
                <span className={`rounded-md border px-2.5 py-1 text-xs font-semibold ${denseLikelyUnavailable ? "border-amber-300/30 bg-amber-300/10 text-amber-100" : "border-emerald-300/20 bg-emerald-300/10 text-emerald-100"}`}>
                  {denseLikelyUnavailable ? "Dense unlikely" : denseLikelyAvailable === true ? "Dense likely available" : "Dense support unknown"}
                </span>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <div>
                  <p className="text-xs text-slate-500">Sparse validation</p>
                  <p className="mt-1 text-sm font-semibold text-white">{sparseStatus === "Sparse Reconstruction Complete" ? "Complete" : "Incomplete"}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">COLMAP detected</p>
                  <p className="mt-1 text-sm font-semibold text-white">{colmapAvailable ? "Yes" : "No"}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Recommended path</p>
                  <p className="mt-1 text-sm font-semibold text-white">{denseRecommendedPath}</p>
                </div>
              </div>
              {(denseReadiness?.reasons ?? []).length > 0 && (
                <div className="mt-4 rounded-md border border-white/10 bg-white/[0.03] p-3">
                  <p className="text-xs font-semibold text-slate-300">Readiness notes</p>
                  <ul className="mt-2 space-y-1 text-xs text-slate-400">
                    {(denseReadiness?.reasons ?? []).map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                </div>
              )}
              {(reconstruction?.lowRegistrationRecommendations ?? []).length > 0 && (
                <div className="mt-4 rounded-md border border-amber-300/20 bg-amber-300/10 p-3">
                  <p className="text-xs font-semibold text-amber-100">Capture recommendations</p>
                  <ul className="mt-2 space-y-1 text-xs text-amber-100/80">
                    {(reconstruction?.lowRegistrationRecommendations ?? []).map((recommendation) => (
                      <li key={recommendation}>{recommendation}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            {showSparseAction && (
              <div className="mt-4 rounded-md border border-brand/25 bg-brand/10 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-md border border-brand/25 bg-slate-950/70 text-brand">
                      {reconstructing ? <Loader2 size={18} className="animate-spin" /> : <Cpu size={18} />}
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-white">Ready for optional sparse validation</p>
                      <p className="mt-1 text-xs text-slate-400">
                        Run COLMAP to generate a sparse validation point cloud.
                      </p>
                    </div>
                  </div>
                  <button
                    disabled={!colmapAvailable || reconstructing}
                    onClick={onRunSparseReconstruction}
                    className="rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-ink hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {reconstructing ? "Running..." : "Run Optional Sparse Validation"}
                  </button>
                </div>
                {!colmapAvailable && (
                  <p className="mt-3 text-sm text-amber-100">COLMAP is required for optional sparse validation.</p>
                )}
              </div>
            )}
            {canRunDense && (
              <div className="mt-4 rounded-md border border-brand/25 bg-brand/10 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">Ready for legacy dense diagnostic</p>
                    <p className="mt-1 text-xs text-slate-400">Dense COLMAP can take much longer than sparse validation, especially without CUDA.</p>
                  </div>
                  <button
                    disabled={denseReconstructing}
                    onClick={onRunDenseReconstruction}
                    className="rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-ink hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {denseReconstructing ? "Running..." : "Run Dense Reconstruction"}
                  </button>
                </div>
                {denseLikelyUnavailable && (
                  <p className="mt-3 text-sm text-amber-100">Your current COLMAP build appears to be without CUDA. Dense reconstruction may fail or be unavailable.</p>
                )}
              </div>
            )}
            {sparseStatus === "Sparse Reconstruction Complete" && denseStatus !== "Dense Reconstruction Complete" && (denseLikelyUnavailable || !denseReady || sparseQualityPoor) && (
              <div className="mt-4 rounded-md border border-amber-300/20 bg-amber-300/10 p-4">
                <p className="text-sm font-semibold text-amber-100">Dense reconstruction is not recommended for this project yet</p>
                <p className="mt-1 text-sm text-amber-100/85">
                  {denseLikelyUnavailable && sparseQualityPoor
                    ? "Dense reconstruction is not available with the current CUDA-less COLMAP build and is not recommended for this weak sparse attempt."
                    : denseLikelyUnavailable
                      ? "Your current COLMAP build appears to be without CUDA. Dense reconstruction may fail or be unavailable."
                    : "Sparse reconstruction exists, but registration quality is too weak for a reliable dense run."}
                </p>
                <details className="mt-3">
                  <summary className="cursor-pointer text-sm font-semibold text-amber-100">Advanced / experimental dense reconstruction</summary>
                  <button
                    disabled={denseReconstructing || denseLikelyUnavailable || !denseReady || sparseQualityPoor}
                    onClick={onRunDenseReconstruction}
                    className="mt-3 rounded-md border border-amber-300/30 px-4 py-2 text-sm font-semibold text-amber-100 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {denseReconstructing ? "Running Dense Reconstruction..." : "Run Dense Reconstruction"}
                  </button>
                </details>
              </div>
            )}
            {reconstructing && !showSparseAction && (
              <div className="mt-4 rounded-md border border-brand/25 bg-brand/10 p-3 text-sm text-cyan-100">
                Running optional sparse validation...
              </div>
            )}
            {reconstruction?.status === "Sparse Reconstruction Complete" && hasPointCloud && (
              <div className="mt-4 rounded-md border border-emerald-300/20 bg-emerald-300/10 p-3 text-sm text-emerald-100">
                Sparse validation complete. The viewer is rendering the COLMAP sparse validation point cloud.
              </div>
            )}
            {(reconstructionError || reconstruction?.status === "Sparse Reconstruction Failed") && (
              <div className="mt-4 rounded-md border border-red-400/30 bg-red-400/10 p-3 text-sm text-red-100">
                <p className="font-semibold">Sparse validation failed</p>
                <p className="mt-1">{reconstruction?.errorMessage ?? reconstructionError}</p>
                {(reconstruction?.likelyCauses ?? []).length > 0 && (
                  <p className="mt-2 text-xs text-red-100/80">Likely causes: {(reconstruction?.likelyCauses ?? []).join(", ")}.</p>
                )}
              </div>
            )}
            {(denseReconstructionError || reconstruction?.denseStatus === "Dense Reconstruction Failed") && (
              <div className="mt-4 rounded-md border border-red-400/30 bg-red-400/10 p-3 text-sm text-red-100">
                <p className="font-semibold">Dense reconstruction failed</p>
                <p className="mt-1">{reconstruction?.denseErrorMessage ?? denseReconstructionError}</p>
                {(reconstruction?.denseLikelyCauses ?? []).length > 0 && (
                  <p className="mt-2 text-xs text-red-100/80">Likely causes: {(reconstruction?.denseLikelyCauses ?? []).join(", ")}.</p>
                )}
                {denseLogEntries.length > 0 && (
                  <details className="mt-3 rounded-md border border-red-200/10 bg-slate-950/70 p-3">
                    <summary className="cursor-pointer text-xs font-semibold text-red-100/80">Technical dense logs</summary>
                    <div className="mt-3 space-y-2">
                      {denseLogEntries.map(([name, preview]) => (
                        <div key={name} className="rounded-md border border-red-200/10 bg-slate-950/70 p-3">
                          <p className="text-xs font-semibold uppercase text-red-100/80">{name}</p>
                          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs leading-5 text-red-50/80">{preview}</pre>
                        </div>
                      ))}
                    </div>
                  </details>
                )}
                {reconstruction?.detectedSparseModelPath && (
                  <p className="mt-2 text-xs text-red-100/80">Sparse model path: {reconstruction.detectedSparseModelPath}</p>
                )}
                {reconstruction?.denseWorkspacePath && (
                  <p className="mt-1 text-xs text-red-100/80">Dense workspace: {reconstruction.denseWorkspacePath}</p>
                )}
              </div>
            )}
            {(summary?.warnings ?? []).length > 0 && (
              <div className="mt-4 space-y-2">
                {(summary?.warnings ?? []).map((warning) => (
                  <div key={warning} className="flex items-center gap-3 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">
                    <AlertTriangle size={17} />
                    {warning}
                  </div>
                ))}
              </div>
            )}
            {SHOW_LEGACY_VISUAL_PREVIEW && outputSelection === "visual" && (
              <div className="mt-4 rounded-md border border-brand/25 bg-brand/10 p-4">
                {visualManifestReady ? (
                  <div>
                    <p className="text-sm font-semibold text-white">{visualExportStatus === "complete" ? "Gaussian Splat export ready" : visualTrainingStatus === "running" || visualTrainingStatus === "queued" ? "Visual Preview training running" : visualTrainingStatus === "complete" ? "Visual Preview training complete" : "Visual Preview manifest ready"}</p>
                    <p className="mt-1 text-sm text-cyan-50/85">Prepared from attempt {visualManifest?.sourceAttemptId} with {visualReadiness?.registeredImageCount ?? 0} registered images and {visualReadiness?.sparsePointCount ?? 0} sparse points.</p>
                    <p className="mt-2 break-all text-xs text-cyan-50/70">{visualManifest?.manifestPath}</p>
                    {visualTraining?.recentTrainingLog && (
                      <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded-md border border-white/10 bg-black/30 p-3 text-xs text-slate-300">{visualTraining.recentTrainingLog}</pre>
                    )}
                    {visualTraining?.splatOutputPath && (
                      <p className="mt-3 break-all text-sm text-emerald-100">Output: {visualTraining.splatOutputPath}</p>
                    )}
                    {visualExportStatus === "complete" && (
                      <p className="mt-2 text-sm text-amber-100">In-browser splat rendering will be added next.</p>
                    )}
                    {visualTrainingStatus === "not_started" && (
                      <button
                        type="button"
                        disabled={visualPreparing}
                        onClick={onTrainVisualPreview}
                        className="mt-4 rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-ink hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {visualPreparing ? "Starting..." : "Train Visual Preview"}
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">Prepare Visual Preview from best sparse attempt</p>
                      <p className="mt-1 text-xs text-slate-300">
                        This creates a manifest for future visual reconstruction training. It does not render or train Gaussian Splat output.
                      </p>
                      {(visualReadiness?.reasons ?? []).length > 0 && (
                        <p className="mt-2 text-xs text-amber-100">Not recommended yet: {visualReadiness?.reasons.join(" ")}</p>
                      )}
                    </div>
                    <button
                      type="button"
                      disabled={!visualReady || visualPreparing}
                      onClick={onPrepareVisualPreview}
                      className="rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-ink hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {visualPreparing ? "Preparing..." : "Prepare Visual Preview"}
                    </button>
                  </div>
                )}
                {visualPreviewError && <p className="mt-3 text-sm text-red-100">{visualPreviewError}</p>}
              </div>
            )}
            {frames.length > 0 && (
              <div className="mt-4">
                <div className="grid gap-3 md:grid-cols-3">
                  {selectedFramePreviews.map((frame, index) => (
                    <div key={`${frame.filename}-${index}`} className="overflow-hidden rounded-md border border-white/10 bg-slate-950">
                      <img src={`${API_BASE}${frame.thumbnailUrl}`} alt={frame.filename} className="h-20 w-full object-cover" />
                      <div className="px-2 py-2">
                        <p className="text-xs font-semibold text-slate-300">{index === 0 ? "First frame" : index === 1 ? "Middle frame" : "Last frame"}</p>
                        <p className="mt-1 truncate text-xs text-slate-500">{frame.filename}</p>
                      </div>
                    </div>
                  ))}
                </div>
                <details className="mt-3">
                  <summary className="cursor-pointer rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm font-semibold text-slate-200">
                    Show all frames
                  </summary>
                  <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
                    {frames.map((frame) => (
                      <div key={frame.filename} className="overflow-hidden rounded-md border border-white/10 bg-slate-950">
                        <img src={`${API_BASE}${frame.thumbnailUrl}`} alt={frame.filename} className="h-20 w-full object-cover" />
                        <p className="truncate px-2 py-2 text-xs text-slate-500">{frame.filename}</p>
                      </div>
                    ))}
                  </div>
                </details>
              </div>
            )}
          </div>
          {hasPointCloud && (
            <div className="glass-panel mb-5 rounded-lg p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">Point cloud readability</p>
                  <p className="mt-1 text-xs text-slate-400">Adjust point rendering and orientation without changing reconstruction data.</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setPresentationMode((current) => !current)}
                    className={`rounded-md border px-3 py-2 text-sm font-medium ${presentationMode ? "border-brand bg-brand/10 text-white" : "border-white/10 text-slate-100 hover:bg-white/10"}`}
                  >
                    {presentationMode ? "Exit presentation mode" : "Presentation mode"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewerResetKey((current) => current + 1)}
                    className="rounded-md border border-white/10 px-3 py-2 text-sm font-medium text-slate-100 hover:bg-white/10"
                  >
                    Center point cloud
                  </button>
                </div>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                {([
                  ["auto", "Auto"],
                  ["interior", "Interior / room scan"],
                  ["exterior", "Exterior / building scan"]
                ] as const).map(([mode, label]) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setScanPreviewMode(mode)}
                    className={`rounded-md border px-3 py-2 text-sm font-medium ${scanPreviewMode === mode ? "border-brand bg-brand/10 text-white" : "border-white/10 text-slate-300 hover:bg-white/10"}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="mt-4 rounded-md border border-white/10 bg-white/[0.03] p-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">Orientation</p>
                    <p className="mt-1 text-xs text-slate-400">COLMAP scale and up direction are arbitrary. Save a correction per attempt.</p>
                  </div>
                  <button type="button" onClick={autoOrient} className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-100 hover:bg-white/10">
                    Auto orient point cloud
                  </button>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" onClick={() => rotate("rotationX", 90)} className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 hover:bg-white/10">Rotate X +90</button>
                  <button type="button" onClick={() => rotate("rotationX", -90)} className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 hover:bg-white/10">Rotate X -90</button>
                  <button type="button" onClick={() => rotate("rotationY", 90)} className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 hover:bg-white/10">Rotate Y +90</button>
                  <button type="button" onClick={() => rotate("rotationY", -90)} className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 hover:bg-white/10">Rotate Y -90</button>
                  <button type="button" onClick={() => rotate("rotationZ", 90)} className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 hover:bg-white/10">Rotate Z +90</button>
                  <button type="button" onClick={() => rotate("rotationZ", -90)} className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 hover:bg-white/10">Rotate Z -90</button>
                  <button type="button" onClick={() => flip("flipX")} className={`rounded-md border px-3 py-2 text-sm ${viewerTransform.flipX ? "border-brand bg-brand/10 text-white" : "border-white/10 text-slate-200 hover:bg-white/10"}`}>Flip X</button>
                  <button type="button" onClick={() => flip("flipY")} className={`rounded-md border px-3 py-2 text-sm ${viewerTransform.flipY ? "border-brand bg-brand/10 text-white" : "border-white/10 text-slate-200 hover:bg-white/10"}`}>Flip Y</button>
                  <button type="button" onClick={() => flip("flipZ")} className={`rounded-md border px-3 py-2 text-sm ${viewerTransform.flipZ ? "border-brand bg-brand/10 text-white" : "border-white/10 text-slate-200 hover:bg-white/10"}`}>Flip Z</button>
                  <button type="button" onClick={resetOrientation} className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 hover:bg-white/10">Reset orientation</button>
                  <button type="button" disabled={!selectedAttempt?.attemptId || savingViewerTransform} onClick={onSaveOrientation} className="rounded-md bg-brand px-3 py-2 text-sm font-semibold text-ink hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50">
                    {savingViewerTransform ? "Saving..." : "Save orientation for this attempt"}
                  </button>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-3">
                {hasDensePointCloud && hasSparsePointCloud && (
                  <div className="flex rounded-md border border-white/10 bg-slate-950/60 p-1">
                    {([
                      ["auto", "Best"],
                      ["dense", "Dense"],
                      ["sparse", "Sparse"]
                    ] as const).map(([mode, label]) => (
                      <button
                        key={mode}
                        type="button"
                        onClick={() => setViewerMode(mode)}
                        className={`rounded px-3 py-1.5 text-sm ${viewerMode === mode ? "bg-brand text-ink" : "text-slate-300 hover:bg-white/10"}`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                )}
                <div className="flex rounded-md border border-white/10 bg-slate-950/60 p-1">
                  {(["Small", "Medium", "Large"] as PointCloudPointSize[]).map((size) => (
                    <button
                      key={size}
                      type="button"
                      onClick={() => setPointSize(size)}
                      className={`rounded px-3 py-1.5 text-sm ${pointSize === size ? "bg-brand text-ink" : "text-slate-300 hover:bg-white/10"}`}
                    >
                      {size}
                    </button>
                  ))}
                </div>
                <label className="flex min-w-48 flex-col gap-1 rounded-md border border-white/10 bg-slate-950/60 px-3 py-2 text-xs text-slate-400">
                  Point size
                  <input type="range" min="0.01" max="0.14" step="0.005" value={pointSizeValue} onChange={(event) => setPointSizeValue(Number(event.target.value))} />
                </label>
                <label className="flex min-w-48 flex-col gap-1 rounded-md border border-white/10 bg-slate-950/60 px-3 py-2 text-xs text-slate-400">
                  Point opacity
                  <input type="range" min="0.15" max="1" step="0.05" value={pointOpacity} onChange={(event) => setPointOpacity(Number(event.target.value))} />
                </label>
                <select value={colorMode} onChange={(event) => setColorMode(event.target.value as PointCloudColorMode)} className="rounded-md border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white">
                  <option value="rgb">RGB from COLMAP</option>
                  <option value="height">Height coloring</option>
                  <option value="depth">Depth coloring</option>
                  <option value="solid">Solid color</option>
                </select>
                {activePointCloud?.source === "colmap_sparse" && (
                  <>
                    {([ 
                      ["Sparse points", showSparsePoints, setShowSparsePoints],
                      ...(activePreviewMode === "interior" ? [["Room bounds", showRoomBounds, setShowRoomBounds], ["Estimated floor", showEstimatedFloor, setShowEstimatedFloor]] as const : []),
                      ["Camera path", showCameraPath, setShowCameraPath]
                    ] as const).map(([label, enabled, setter]) => (
                      <button
                        key={label}
                        type="button"
                        onClick={() => setter((current) => !current)}
                        className={`rounded-md border px-3 py-2 text-sm font-medium ${
                          enabled ? "border-brand bg-brand/10 text-white" : "border-white/10 text-slate-300 hover:bg-white/10"
                        }`}
                      >
                        {enabled ? `Hide ${label}` : `Show ${label}`}
                      </button>
                    ))}
                  </>
                )}
                {activePointCloud?.source === "colmap_sparse" && (
                  <>
                    <button
                      type="button"
                      onClick={() => setDebugCameraPath((current) => !current)}
                      className={`rounded-md border px-3 py-2 text-sm font-medium ${debugCameraPath ? "border-brand bg-brand/10 text-white" : "border-white/10 text-slate-300 hover:bg-white/10"}`}
                    >
                      {debugCameraPath ? "Hide debug camera path" : "Show debug camera path"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowCameraSpheres((current) => !current)}
                      className={`rounded-md border px-3 py-2 text-sm font-medium ${showCameraSpheres ? "border-brand bg-brand/10 text-white" : "border-white/10 text-slate-300 hover:bg-white/10"}`}
                    >
                      {showCameraSpheres ? "Hide camera spheres" : "Show camera spheres"}
                    </button>
                    <label className="flex min-w-48 flex-col gap-1 rounded-md border border-white/10 bg-slate-950/60 px-3 py-2 text-xs text-slate-400">
                      Camera path size
                      <input type="range" min="0.01" max="0.09" step="0.002" value={cameraPathPointSize} onChange={(event) => setCameraPathPointSize(Number(event.target.value))} />
                    </label>
                    <label className="flex min-w-48 flex-col gap-1 rounded-md border border-white/10 bg-slate-950/60 px-3 py-2 text-xs text-slate-400">
                      Camera path opacity
                      <input type="range" min="0.05" max="1" step="0.05" value={cameraPathPointOpacity} onChange={(event) => setCameraPathPointOpacity(Number(event.target.value))} />
                    </label>
                    <label className="flex min-w-48 flex-col gap-1 rounded-md border border-white/10 bg-slate-950/60 px-3 py-2 text-xs text-slate-400">
                      Camera line opacity
                      <input type="range" min="0.05" max="1" step="0.05" value={cameraPathLineOpacity} onChange={(event) => setCameraPathLineOpacity(Number(event.target.value))} />
                    </label>
                  </>
                )}
                <button
                  type="button"
                  onClick={() => setShowBoundingBox((current) => !current)}
                  className={`rounded-md border px-3 py-2 text-sm font-medium ${showBoundingBox ? "border-brand bg-brand/10 text-white" : "border-white/10 text-slate-300 hover:bg-white/10"}`}
                >
                  {showBoundingBox ? "Hide bounding box" : "Show bounding box"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowReference((current) => !current)}
                  className={`rounded-md border px-3 py-2 text-sm font-medium ${
                    showReference ? "border-brand bg-brand/10 text-white" : "border-white/10 text-slate-300 hover:bg-white/10"
                  }`}
                >
                  {showReference ? "Hide floor/grid reference" : "Show floor/grid reference"}
                </button>
              </div>
            </div>
          )}
          {SHOW_LEGACY_VISUAL_PREVIEW && outputSelection === "visual" ? (
            <div className="flex h-[540px] items-center justify-center rounded-lg border border-white/10 bg-slate-950 p-8 text-center shadow-glow">
              <div>
                <p className="text-xl font-semibold text-white">{visualExportStatus === "complete" ? "Gaussian Splat export ready" : visualTrainingStatus === "running" || visualTrainingStatus === "queued" ? "Visual Preview training running" : visualManifestReady ? "Visual Preview manifest ready" : "Visual Preview not prepared"}</p>
                <p className="mt-2 max-w-lg text-sm leading-6 text-slate-400">
                  {visualExportStatus === "complete"
                    ? `Exported output: ${visualTraining?.splatOutputPath ?? visualManifest?.splatOutputPath ?? "available in project storage"}.`
                    : visualManifestReady
                    ? `Inputs prepared from the best sparse attempt: ${visualReadiness?.registeredImageCount ?? 0} registered images, ${visualReadiness?.sparsePointCount ?? 0} sparse points.`
                    : "Prepare Visual Preview from the best sparse attempt when readiness checks pass."}
                </p>
                <p className="mt-3 text-sm text-amber-100">In-browser splat rendering will be added next.</p>
              </div>
            </div>
          ) : (
            <ViewerScene
              pointCloud={activePointCloud}
              sceneAnalysis={activeSceneAnalysis}
              pointSize={pointSize}
              pointSizeValue={pointSizeValue}
              pointOpacity={pointOpacity}
              colorMode={colorMode}
              showSparsePoints={showSparsePoints}
              showRoomBounds={activePreviewMode === "interior" && showRoomBounds}
              showEstimatedFloor={activePreviewMode === "interior" && showEstimatedFloor}
              showCameraPath={renderCameraPath}
              showBoundingBox={renderBoundingBox}
              showReference={renderReference}
              showAxisGizmo={activePreviewMode === "exterior" && debugCameraPath && !presentationMode}
              viewerTransform={viewerTransform}
              previewMode={activePreviewMode}
              presentationMode={presentationMode}
              cameraPathPointSize={cameraPathPointSize}
              cameraPathPointOpacity={cameraPathPointOpacity}
              cameraPathLineOpacity={cameraPathLineOpacity}
              showCameraSpheres={showCameraSpheres}
              outputLabel={outputSelection === "dense" ? "Dense / geometric model" : outputType}
              resetKey={viewerResetKey}
            />
          )}
        </section>

        <aside className="glass-panel rounded-lg p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold text-white">{project?.name ?? "Project info"}</h2>
              <p className="mt-1 text-sm text-slate-400">{project?.site_type ?? "Interior capture"}</p>
            </div>
            {project && <StatusBadge status={project.status} />}
          </div>

          <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
              <dt className="text-slate-500">Type</dt>
              <dd className="mt-1 text-slate-200">{project?.scan_type ?? "Interior Prototype"}</dd>
            </div>
            <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
              <dt className="text-slate-500">Media</dt>
              <dd className="mt-1 text-slate-200">{project?.mediaCount ?? project?.media?.length ?? 0}</dd>
            </div>
          </dl>

          <Link href={`/projects/${params.id}/report`} className="mt-5 flex w-full justify-center rounded-md border border-white/10 px-4 py-2.5 text-sm font-medium text-slate-100 hover:bg-white/10">
            Generate Scan Summary
          </Link>

          <div className="mt-7 border-t border-white/10 pt-5">
            <h3 className="font-semibold text-white">Annotations</h3>
            <div className="mt-4 space-y-3">
              {annotations.map((annotation) => (
                <div key={annotation.id} className="rounded-md border border-white/10 bg-slate-950/70 p-3 text-sm text-slate-200">
                  {annotation.text}
                </div>
              ))}
            </div>
            <form onSubmit={submitNote} className="mt-4 flex gap-2">
              <input value={note} onChange={(event) => setNote(event.target.value)} className="min-w-0 flex-1 rounded-md border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-brand" placeholder="Add inspection note" />
              <button className="rounded-md bg-brand px-3 text-ink hover:bg-cyan-200" aria-label="Add annotation">
                <Plus size={18} />
              </button>
            </form>
          </div>
        </aside>
      </div>
    </AppShell>
  );
}
