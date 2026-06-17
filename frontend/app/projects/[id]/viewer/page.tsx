"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/StatusBadge";
import { PointCloudPointSize, ViewerScene } from "@/components/ViewerScene";
import { API_BASE, addAnnotation, getCaptureSummary, getDensePointCloud, getDiagnostics, getFrames, getPointCloud, getProject, getReconstructionSummary, getSceneAnalysis, listAnnotations, runDenseReconstruction, runSparseReconstruction } from "@/lib/api";
import type { Annotation, CaptureSummary, Diagnostics, FramePreview, PointCloudResponse, Project, ReconstructionSummary, SceneAnalysis } from "@/lib/types";
import { AlertTriangle, Cpu, FileText, Loader2, Plus } from "lucide-react";

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
  const [sceneAnalysis, setSceneAnalysis] = useState<SceneAnalysis | null>(null);
  const [reconstructing, setReconstructing] = useState(false);
  const [denseReconstructing, setDenseReconstructing] = useState(false);
  const [reconstructionError, setReconstructionError] = useState("");
  const [denseReconstructionError, setDenseReconstructionError] = useState("");
  const [viewerMode, setViewerMode] = useState<"auto" | "dense" | "sparse">("auto");
  const [pointSize, setPointSize] = useState<PointCloudPointSize>("Medium");
  const [showSparsePoints, setShowSparsePoints] = useState(true);
  const [showRoomBounds, setShowRoomBounds] = useState(true);
  const [showEstimatedFloor, setShowEstimatedFloor] = useState(true);
  const [showCameraPath, setShowCameraPath] = useState(true);
  const [showReference, setShowReference] = useState(true);
  const [viewerResetKey, setViewerResetKey] = useState(0);
  const [note, setNote] = useState("");

  useEffect(() => {
    getProject(params.id).then(setProject).catch(() => setProject(null));
    listAnnotations(params.id).then(setAnnotations).catch(() => setAnnotations([]));
    getCaptureSummary(params.id).then(setSummary).catch(() => setSummary(null));
    getFrames(params.id).then(setFrames).catch(() => setFrames([]));
    getDiagnostics().then(setDiagnostics).catch(() => setDiagnostics(null));
    refreshReconstruction();
  }, [params.id]);

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
        loadedSparse = await getPointCloud(params.id).catch(() => null);
        loadedSceneAnalysis = await getSceneAnalysis(params.id).catch(() => null);
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
  const showSparseAction = inputFrameCount > 0 && sparseNotStarted;
  const denseReadiness = reconstruction?.denseReadiness;
  const denseReady = denseReadiness?.ready ?? true;
  const canRunDense = sparseStatus === "Sparse Reconstruction Complete" && denseStatus !== "Dense Reconstruction Complete" && colmapAvailable && !denseLikelyUnavailable && denseReady;
  const denseRecommendedPath = denseLikelyUnavailable
    ? "Continue with sparse scene preview or install a CUDA-enabled COLMAP build"
    : denseReadiness && !denseReadiness.ready
      ? "Retry dense reconstruction with better capture"
    : sparseStatus !== "Sparse Reconstruction Complete"
      ? "Continue with sparse preview"
      : denseStatus === "Dense Reconstruction Failed"
        ? "Use a visual preview pipeline such as Gaussian Splatting"
        : "Retry dense reconstruction with better capture";
  const denseLogEntries = Object.entries(reconstruction?.denseLogPreviewSummary ?? {}).filter(([, value]) => value.trim().length > 0);
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
  const outputType = activePointCloud?.source === "colmap_dense" ? "Dense point cloud preview" : sparseSceneAvailable ? "Sparse scene preview" : activePointCloud?.source === "colmap_sparse" ? "Sparse point cloud preview" : "No reconstruction output";
  const hasPointCloud = Boolean(activePointCloud?.available && activePointCloud.points.length > 0);
  const title = activePointCloud?.source === "colmap_dense" ? "Dense Point Cloud Preview" : sparseSceneAvailable ? "Sparse Scene Preview" : hasPointCloud ? "Sparse Point Cloud Preview" : "No Reconstruction Output Yet";
  const explanation = activePointCloud?.source === "colmap_dense"
    ? "This is a denser COLMAP point cloud reconstructed from the uploaded capture. It is not a mesh or final digital twin yet."
    : sparseSceneAvailable
      ? "This view uses the real COLMAP sparse reconstruction plus estimated room bounds to make the captured space easier to inspect. It is not a dense mesh yet."
      : hasPointCloud
        ? "This is a real sparse point cloud reconstructed from the uploaded capture. It is not a dense mesh yet."
    : "Upload media, process capture, then run sparse reconstruction to generate a real preview.";
  const registeredImageCount = reconstruction?.registeredImageCount ?? 0;
  const registrationRatioLabel = reconstruction?.registrationRatioLabel ?? "0%";
  const sparseQualityLabel = reconstruction?.sparseQualityLabel ?? "Not Started";
  const room = sceneAnalysis?.roomScaffold;
  const denseAvailabilityText = denseLikelyUnavailable
    ? "Dense reconstruction requires a CUDA-enabled COLMAP build on this machine."
    : denseLikelyAvailable === true
      ? "Dense reconstruction support appears available."
      : "Dense reconstruction support is unknown on this machine.";

  return (
    <AppShell>
      <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
        <section>
          <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm text-brand">Future Inspection Viewer</p>
              <h1 className="mt-2 text-3xl font-semibold text-white">{title}</h1>
              <p className="mt-2 text-sm text-slate-400">
                {explanation}
              </p>
            </div>
            <Link href={`/projects/${params.id}/report`} className="inline-flex items-center gap-2 rounded-md bg-brand px-4 py-2.5 font-semibold text-ink hover:bg-cyan-200">
              <FileText size={17} /> Export Report
            </Link>
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
              Next action: {reconstruction?.recommendedNextAction ?? "Run sparse reconstruction"}
            </div>
            {sparseSceneAvailable && (
              <div className="mt-4 rounded-md border border-white/10 bg-slate-950/60 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">Sparse Scene Stats</p>
                    <p className="mt-1 text-xs text-slate-400">The preview combines sparse COLMAP points with estimated room bounds.</p>
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
                    <p className="text-xs text-slate-500">Width</p>
                    <p className="mt-1 text-sm font-semibold text-white">{room ? room.width.toFixed(2) : "-"} units</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Depth</p>
                    <p className="mt-1 text-sm font-semibold text-white">{room ? room.depth.toFixed(2) : "-"} units</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Height</p>
                    <p className="mt-1 text-sm font-semibold text-white">{room ? room.height.toFixed(2) : "-"} units</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Camera path</p>
                    <p className="mt-1 text-sm font-semibold text-white">{sceneAnalysis?.cameraPath.available ? `${sceneAnalysis.cameraPath.positions.length} poses` : "Unavailable"}</p>
                  </div>
                </div>
                <div className="mt-3 rounded-md border border-white/10 bg-white/[0.03] p-3 text-xs text-slate-300">
                  {denseAvailabilityText} Next step: Install CUDA-enabled COLMAP or continue with visual preview pipeline.
                </div>
              </div>
            )}
            <div className="mt-4 rounded-md border border-white/10 bg-slate-950/60 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">Dense Readiness</p>
                  <p className="mt-1 text-xs text-slate-400">{colmapCudaHint}</p>
                </div>
                <span className={`rounded-md border px-2.5 py-1 text-xs font-semibold ${denseLikelyUnavailable ? "border-amber-300/30 bg-amber-300/10 text-amber-100" : "border-emerald-300/20 bg-emerald-300/10 text-emerald-100"}`}>
                  {denseLikelyUnavailable ? "Dense unlikely" : denseLikelyAvailable === true ? "Dense likely available" : "Dense support unknown"}
                </span>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <div>
                  <p className="text-xs text-slate-500">Sparse reconstruction</p>
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
                      <p className="text-sm font-semibold text-white">Ready for sparse reconstruction</p>
                      <p className="mt-1 text-xs text-slate-400">
                        Run COLMAP to generate a real sparse point cloud preview.
                      </p>
                    </div>
                  </div>
                  <button
                    disabled={!colmapAvailable || reconstructing}
                    onClick={onRunSparseReconstruction}
                    className="rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-ink hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {reconstructing ? "Running COLMAP sparse reconstruction..." : "Run Sparse Reconstruction"}
                  </button>
                </div>
                {!colmapAvailable && (
                  <p className="mt-3 text-sm text-amber-100">COLMAP is required for sparse reconstruction.</p>
                )}
              </div>
            )}
            {canRunDense && (
              <div className="mt-4 rounded-md border border-brand/25 bg-brand/10 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">Ready for dense reconstruction</p>
                    <p className="mt-1 text-xs text-slate-400">Dense reconstruction can take much longer than sparse reconstruction, especially without CUDA.</p>
                  </div>
                  <button
                    disabled={denseReconstructing}
                    onClick={onRunDenseReconstruction}
                    className="rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-ink hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {denseReconstructing ? "Running Dense Reconstruction..." : "Run Dense Reconstruction"}
                  </button>
                </div>
                {denseLikelyUnavailable && (
                  <p className="mt-3 text-sm text-amber-100">Your current COLMAP build appears to be without CUDA. Dense reconstruction may fail or be unavailable.</p>
                )}
              </div>
            )}
            {sparseStatus === "Sparse Reconstruction Complete" && denseStatus !== "Dense Reconstruction Complete" && (denseLikelyUnavailable || !denseReady) && (
              <div className="mt-4 rounded-md border border-amber-300/20 bg-amber-300/10 p-4">
                <p className="text-sm font-semibold text-amber-100">Dense reconstruction is not recommended for this project yet</p>
                <p className="mt-1 text-sm text-amber-100/85">
                  {denseLikelyUnavailable
                    ? "Your current COLMAP build appears to be without CUDA. Dense reconstruction may fail or be unavailable."
                    : "Sparse reconstruction exists, but registration quality is too weak for a reliable dense run."}
                </p>
                <button
                  disabled={denseReconstructing || denseLikelyUnavailable || !denseReady}
                  onClick={onRunDenseReconstruction}
                  className="mt-3 rounded-md border border-amber-300/30 px-4 py-2 text-sm font-semibold text-amber-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {denseReconstructing ? "Running Dense Reconstruction..." : "Run Dense Reconstruction"}
                </button>
              </div>
            )}
            {reconstructing && (
              <div className="mt-4 rounded-md border border-brand/25 bg-brand/10 p-3 text-sm text-cyan-100">
                Running COLMAP sparse reconstruction...
              </div>
            )}
            {reconstruction?.status === "Sparse Reconstruction Complete" && hasPointCloud && (
              <div className="mt-4 rounded-md border border-emerald-300/20 bg-emerald-300/10 p-3 text-sm text-emerald-100">
                Sparse reconstruction complete. The viewer is now rendering the COLMAP sparse point cloud.
              </div>
            )}
            {(reconstructionError || reconstruction?.status === "Sparse Reconstruction Failed") && (
              <div className="mt-4 rounded-md border border-red-400/30 bg-red-400/10 p-3 text-sm text-red-100">
                <p className="font-semibold">Sparse reconstruction failed</p>
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
            {frames.length > 0 && (
              <div className="mt-4 grid grid-cols-4 gap-2">
                {frames.slice(0, 4).map((frame) => (
                  <img key={frame.filename} src={`${API_BASE}${frame.thumbnailUrl}`} alt={frame.filename} className="h-20 w-full rounded-md border border-white/10 object-cover" />
                ))}
              </div>
            )}
          </div>
          {hasPointCloud && (
            <div className="glass-panel mb-5 rounded-lg p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">Point cloud readability</p>
                  <p className="mt-1 text-xs text-slate-400">Adjust point rendering without changing reconstruction data.</p>
                </div>
                <button
                  type="button"
                  onClick={() => setViewerResetKey((current) => current + 1)}
                  className="rounded-md border border-white/10 px-3 py-2 text-sm font-medium text-slate-100 hover:bg-white/10"
                >
                  Center point cloud
                </button>
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
                {activePointCloud?.source === "colmap_sparse" && (
                  <>
                    {([
                      ["Sparse points", showSparsePoints, setShowSparsePoints],
                      ["Room bounds", showRoomBounds, setShowRoomBounds],
                      ["Estimated floor", showEstimatedFloor, setShowEstimatedFloor],
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
          <ViewerScene
            pointCloud={activePointCloud}
            sceneAnalysis={activeSceneAnalysis}
            pointSize={pointSize}
            showSparsePoints={showSparsePoints}
            showRoomBounds={showRoomBounds}
            showEstimatedFloor={showEstimatedFloor}
            showCameraPath={showCameraPath}
            showReference={showReference}
            resetKey={viewerResetKey}
          />
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
