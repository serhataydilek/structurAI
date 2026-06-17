"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { API_BASE, getCaptureSummary, getDiagnostics, getFrames, getProcessingStatus, getProject, getReconstructionSummary, runDenseReconstruction, runSparseReconstruction, startProcessing } from "@/lib/api";
import type { CaptureSummary, Diagnostics, ExtractionFpsMode, FramePreview, ProcessingStatus, Project, ReconstructionMatchingMode, ReconstructionSummary } from "@/lib/types";
import { AlertTriangle, Check, Cpu, ImageIcon, Loader2 } from "lucide-react";

export default function ProcessingPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const [project, setProject] = useState<Project | null>(null);
  const [status, setStatus] = useState<ProcessingStatus | null>(null);
  const [summary, setSummary] = useState<CaptureSummary | null>(null);
  const [frames, setFrames] = useState<FramePreview[]>([]);
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null);
  const [reconstruction, setReconstruction] = useState<ReconstructionSummary | null>(null);
  const [reconstructing, setReconstructing] = useState(false);
  const [denseReconstructing, setDenseReconstructing] = useState(false);
  const [reconstructionError, setReconstructionError] = useState("");
  const [denseReconstructionError, setDenseReconstructionError] = useState("");
  const [matchingMode, setMatchingMode] = useState<ReconstructionMatchingMode>("Auto");
  const [autoProcessing, setAutoProcessing] = useState(false);
  const [largeFrame, setLargeFrame] = useState<FramePreview | null>(null);
  const [showAllFrames, setShowAllFrames] = useState(false);

  useEffect(() => {
    getProject(params.id).then(setProject).catch(() => setProject(null));
    getDiagnostics().then(setDiagnostics).catch(() => setDiagnostics(null));
    getReconstructionSummary(params.id).then(setReconstruction).catch(() => setReconstruction(null));
  }, [params.id]);

  useEffect(() => {
    if (searchParams.get("autostart") !== "1") return;
    let active = true;
    setAutoProcessing(true);
    setStatus({
      projectId: params.id,
      status: "Processing",
      progress: 20,
      currentStep: "Extracting frames",
      steps: ["Upload complete", "Extracting frames", "Analyzing capture quality", "Preparing reconstruction workspace", "Ready for sparse reconstruction"],
      workspacePrepared: false,
      extractedFrameCount: 0,
      selectedFpsMode: (searchParams.get("fps") as ExtractionFpsMode) ?? "Balanced",
      extractionFps: 2,
      warnings: [],
      readinessLabel: "Poor Capture"
    });
    startProcessing(params.id, { extractionFpsMode: (searchParams.get("fps") as ExtractionFpsMode) ?? "Balanced" })
      .then((next) => {
        if (!active) return;
        setStatus(next);
        getCaptureSummary(params.id).then(setSummary).catch(() => setSummary(null));
        getFrames(params.id).then(setFrames).catch(() => setFrames([]));
        getProject(params.id).then(setProject).catch(() => undefined);
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) setAutoProcessing(false);
      });
    return () => {
      active = false;
    };
  }, [params.id, searchParams]);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      const next = await getProcessingStatus(params.id);
      if (!active) return;
      setStatus(next);
      if (next.status === "Processing") {
        window.setTimeout(poll, 1400);
      } else {
        getCaptureSummary(params.id).then(setSummary).catch(() => setSummary(null));
        getFrames(params.id).then(setFrames).catch(() => setFrames([]));
        getReconstructionSummary(params.id).then(setReconstruction).catch(() => setReconstruction(null));
      }
    };
    poll().catch(() => undefined);
    return () => {
      active = false;
    };
  }, [params.id]);

  const progress = status?.progress ?? 0;
  const hasFrames = (summary?.extractedFrameCount ?? status?.extractedFrameCount ?? 0) > 0;
  const colmapAvailable = diagnostics?.colmap.colmapAvailable ?? false;
  const denseLikelyAvailable = reconstruction?.denseReconstructionLikelyAvailable ?? diagnostics?.colmap.denseReconstructionLikelyAvailable ?? "unknown";
  const colmapCudaHint = reconstruction?.colmapCudaHint ?? diagnostics?.colmap.colmapCudaHint ?? (colmapAvailable ? "COLMAP detected; CUDA dense-stereo support is unknown." : "COLMAP not detected.");
  const denseLikelyUnavailable = denseLikelyAvailable === false;
  const sparseComplete = reconstruction?.sparseStatus === "Sparse Reconstruction Complete" || reconstruction?.status === "Sparse Reconstruction Complete";
  const denseComplete = reconstruction?.denseStatus === "Dense Reconstruction Complete";
  const denseReadiness = reconstruction?.denseReadiness;
  const sparseQualityPoor = reconstruction?.sparseQualityLabel === "Poor Sparse Reconstruction";
  const canRunDense = sparseComplete && !denseComplete && colmapAvailable && !denseLikelyUnavailable && (denseReadiness?.ready ?? true);
  const denseRecommendedPath = denseLikelyUnavailable
    ? "Continue with sparse scene preview or install a CUDA-enabled COLMAP build"
    : !sparseComplete
      ? "Continue with sparse preview"
      : reconstruction?.denseStatus === "Dense Reconstruction Failed"
        ? "Use a visual preview pipeline such as Gaussian Splatting"
        : "Retry dense reconstruction with better capture";
  const denseLogEntries = Object.entries(reconstruction?.denseLogPreviewSummary ?? {}).filter(([, value]) => value.trim().length > 0);
  const attempts = reconstruction?.reconstructionAttempts ?? [];
  const bestAttempt = reconstruction?.bestAttempt;
  const latestAttempt = reconstruction?.latestAttempt;
  const selectedFrames = frames.length > 0
    ? [frames[0], frames[Math.floor(frames.length / 2)], frames[frames.length - 1]].filter((frame, index, all) => frame && all.findIndex((item) => item.filename === frame.filename) === index)
    : [];

  async function onRunSparseReconstruction() {
    setReconstructing(true);
    setReconstructionError("");
    setReconstruction((current) => current ? { ...current, status: "Reconstructing Sparse Model" } : current);
    try {
      const result = await runSparseReconstruction(params.id, { matchingMode });
      setReconstruction(result);
      getProject(params.id).then(setProject).catch(() => undefined);
    } catch (error) {
      setReconstructionError(error instanceof Error ? error.message : "Sparse reconstruction failed");
      getReconstructionSummary(params.id).then(setReconstruction).catch(() => undefined);
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
      const result = await runDenseReconstruction(params.id);
      setReconstruction(result);
      getProject(params.id).then(setProject).catch(() => undefined);
    } catch (error) {
      setDenseReconstructionError(error instanceof Error ? error.message : "Dense reconstruction failed");
      getReconstructionSummary(params.id).then(setReconstruction).catch(() => undefined);
      getProject(params.id).then(setProject).catch(() => undefined);
    } finally {
      setDenseReconstructing(false);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <p className="text-sm text-brand">Capture Processing</p>
        <h1 className="mt-2 text-3xl font-semibold text-white">{project?.name ?? "Scan project"}</h1>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          Structura AI now prepares real capture frames and a reconstruction workspace. COLMAP, OpenMVS, and Blender CLI integration comes next.
        </p>

        <div className="glass-panel mt-8 rounded-lg p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm text-slate-400">Current step</p>
              <p className="mt-1 text-xl font-semibold text-white">{status?.status === "Ready" ? "Capture processing complete" : status?.currentStep ?? "Upload received"}</p>
            </div>
            <div className="text-right">
              <p className="text-3xl font-semibold text-brand">{progress}%</p>
              <p className="text-xs text-slate-400">{status?.status ?? "Draft"}</p>
            </div>
          </div>

          <div className="mt-6 h-2 overflow-hidden rounded-full bg-slate-800">
            <div className="h-full rounded-full bg-brand transition-all duration-700" style={{ width: `${progress}%` }} />
          </div>

          <div className="mt-8 grid gap-3">
            {(status?.steps ?? [
              "Upload complete",
              "Extracting frames",
              "Analyzing capture quality",
              "Preparing reconstruction workspace",
              "Ready for sparse reconstruction"
            ]).map((step, index, steps) => {
              const threshold = Math.round(((index + 1) / steps.length) * 100);
              const complete = progress >= threshold || status?.status === "Ready";
              const active = status?.currentStep === step && !complete;
              return (
                <div key={step} className="flex items-center gap-3 rounded-md border border-white/10 bg-white/[0.03] px-4 py-3">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full border border-white/10 bg-slate-950">
                    {complete ? <Check size={16} className="text-emerald-300" /> : active ? <Loader2 size={16} className="animate-spin text-brand" /> : <span className="h-2 w-2 rounded-full bg-slate-500" />}
                  </span>
                  <span className="text-sm text-slate-200">{step}</span>
                </div>
              );
            })}
          </div>

          {status?.workspacePrepared && (
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href={`/projects/${params.id}/viewer`} className="inline-flex rounded-md bg-brand px-5 py-3 font-semibold text-ink hover:bg-cyan-200">
                Open Future Viewer Preview
              </Link>
              <Link href={`/projects/${params.id}/report`} className="inline-flex rounded-md border border-white/10 px-5 py-3 font-semibold text-slate-100 hover:bg-white/10">
                View Capture Report
              </Link>
            </div>
          )}
          {(autoProcessing || status?.status === "Processing") && (
            <div className="mt-4 rounded-md border border-brand/25 bg-brand/10 p-3 text-sm text-cyan-100">
              Upload complete. Extracting full reconstruction frames and generating preview thumbnails...
            </div>
          )}
        </div>

        <section className="glass-panel mt-6 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-white">Capture Summary</h2>
          <p className="mt-2 text-sm text-slate-400">Actual uploaded media and extracted frames prepared for the reconstruction pipeline.</p>
          <div className="mt-4 grid gap-4 md:grid-cols-5">
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Media uploaded</p>
              <p className="mt-2 text-2xl font-semibold text-white">{summary?.uploadedMediaCount ?? project?.mediaCount ?? 0}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Images</p>
              <p className="mt-2 text-2xl font-semibold text-white">{summary?.imageCount ?? 0}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Videos</p>
              <p className="mt-2 text-2xl font-semibold text-white">{summary?.videoCount ?? 0}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Extracted frames</p>
              <p className="mt-2 text-2xl font-semibold text-white">{summary?.extractedFrameCount ?? status?.extractedFrameCount ?? 0}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Capture readiness</p>
              <p className="mt-2 text-sm font-semibold text-white">{summary?.readinessLabel ?? status?.readinessLabel ?? "Poor Capture"}</p>
            </div>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-4">
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Selected FPS</p>
              <p className="mt-2 text-sm font-semibold text-white">{summary?.selectedFpsMode ?? status?.selectedFpsMode ?? "Balanced"} ({summary?.extractionFps ?? status?.extractionFps ?? 2} FPS)</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Average sharpness</p>
              <p className="mt-2 text-sm font-semibold text-white">{summary?.sharpnessAvailable ? summary.averageSharpness?.toFixed(2) : "Unavailable"}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Blurry frames</p>
              <p className="mt-2 text-sm font-semibold text-white">{summary?.blurryFrameCount ?? status?.blurryFrameCount ?? 0}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Blurry percentage</p>
              <p className="mt-2 text-sm font-semibold text-white">{summary?.blurryFramePercentage ?? status?.blurryFramePercentage ?? 0}%</p>
            </div>
          </div>
          <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.03] p-4">
            <p className="text-xs text-slate-500">Next technical step</p>
            <p className="mt-2 text-sm font-semibold text-white">Run reconstruction pipeline using COLMAP/OpenMVS</p>
            <p className="mt-2 text-xs text-slate-500">Workspace: {summary?.workspacePrepared || status?.workspacePrepared ? "Prepared" : "Pending"}</p>
          </div>

          {(summary?.warnings ?? status?.warnings ?? []).length > 0 && (
            <div className="mt-5 space-y-3">
              {(summary?.warnings ?? status?.warnings ?? []).map((warning) => (
                <div key={warning} className="flex items-center gap-3 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">
                  <AlertTriangle size={17} />
                  {warning}
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="glass-panel mt-6 rounded-lg p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Cpu size={18} className="text-brand" />
                <h2 className="text-lg font-semibold text-white">Sparse Reconstruction</h2>
              </div>
              <p className="mt-2 max-w-2xl text-sm text-slate-400">
                Sparse reconstruction runs COLMAP feature extraction, matching, and mapper. Dense reconstruction can create a denser point cloud, but it is still not a mesh or final digital twin.
              </p>
            </div>
            <button
              disabled={!hasFrames || !colmapAvailable || reconstructing}
              onClick={onRunSparseReconstruction}
              className="rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-ink hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {reconstructing ? "Running COLMAP..." : "Run Sparse Reconstruction"}
            </button>
          </div>

          <div className="mt-5 rounded-lg border border-white/10 bg-white/[0.03] p-4">
            <p className="text-xs text-slate-500">Reconstruction matching mode</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {(["Auto", "Video Sequential", "Photo Exhaustive"] as ReconstructionMatchingMode[]).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  disabled={reconstructing}
                  onClick={() => setMatchingMode(mode)}
                  className={`rounded-md border px-3 py-2 text-sm font-medium ${
                    matchingMode === mode
                      ? "border-brand bg-brand/10 text-white"
                      : "border-white/10 bg-slate-950/50 text-slate-300 hover:bg-white/10"
                  } disabled:cursor-not-allowed disabled:opacity-60`}
                >
                  {mode}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-slate-500">Auto uses Video Sequential for video captures and Photo Exhaustive for photo-only captures.</p>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-5">
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">COLMAP</p>
              <p className="mt-2 text-sm font-semibold text-white">{colmapAvailable ? "Available" : "Missing"}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Input frames</p>
              <p className="mt-2 text-2xl font-semibold text-white">{reconstruction?.inputFrameCount ?? summary?.extractedFrameCount ?? 0}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Sparse output</p>
              <p className="mt-2 text-sm font-semibold text-white">{reconstruction?.sparseOutputExists ? "Found" : "Not generated"}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Status</p>
              <p className="mt-2 text-sm font-semibold text-white">{reconstruction?.status ?? "Not Started"}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Matching used</p>
              <p className="mt-2 text-sm font-semibold text-white">{reconstruction?.matchingModeUsed ?? "Not Started"}</p>
            </div>
          </div>
          {reconstruction?.sparsePointCloudAvailable && (
            <div className="mt-5 grid gap-4 md:grid-cols-4">
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Registered images</p>
                <p className="mt-2 text-2xl font-semibold text-white">{reconstruction.registeredImageCount ?? 0}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Registration ratio</p>
                <p className="mt-2 text-sm font-semibold text-white">{Math.round((reconstruction.registrationRatio ?? 0) * 100)}%</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Sparse quality</p>
                <p className="mt-2 text-sm font-semibold text-white">{reconstruction.sparseQualityLabel ?? "Poor Sparse Reconstruction"}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Sparse points</p>
                <p className="mt-2 text-2xl font-semibold text-white">{reconstruction.sparsePointCount ?? 0}</p>
              </div>
            </div>
          )}

          {!colmapAvailable && (
            <div className="mt-4 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">
              COLMAP is not detected. Install COLMAP and verify with <span className="font-semibold">colmap -h</span> or <span className="font-semibold">COLMAP.bat -h</span>, then restart the backend.
            </div>
          )}
          {!hasFrames && (
            <div className="mt-4 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">
              Process capture media before running sparse reconstruction.
            </div>
          )}
          {reconstruction?.status === "Sparse Reconstruction Complete" && (
            <div className="mt-4 rounded-md border border-emerald-300/20 bg-emerald-300/10 p-3 text-sm text-emerald-100">
              Sparse reconstruction complete. Camera poses and sparse structure were generated. Dense reconstruction is the next milestone.
            </div>
          )}
          {(reconstructionError || reconstruction?.status === "Sparse Reconstruction Failed") && (
            <div className="mt-4 rounded-md border border-red-400/30 bg-red-400/10 p-3 text-sm text-red-100">
              <p className="font-semibold">Sparse reconstruction failed</p>
              <p className="mt-1">{reconstruction?.errorMessage ?? reconstructionError}</p>
              {(reconstruction?.likelyCauses ?? []).length > 0 && (
                <p className="mt-2 text-xs text-red-100/80">Likely causes: {(reconstruction?.likelyCauses ?? []).join(", ")}.</p>
              )}
              {(reconstruction?.recommendedFixes ?? []).length > 0 && (
                <p className="mt-2 text-xs text-red-100/80">Recommended fixes: {(reconstruction?.recommendedFixes ?? []).join(", ")}.</p>
              )}
            </div>
          )}
          {reconstruction?.recommendedNextAction && (
            <div className="mt-4 rounded-md border border-white/10 bg-white/[0.03] p-3 text-sm text-slate-300">
              Recommended next action: {reconstruction.recommendedNextAction}
            </div>
          )}
          {attempts.length > 0 && (
            <div className="mt-5 rounded-md border border-white/10 bg-slate-950/60 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">Reconstruction Attempts</p>
                  <p className="mt-1 text-xs text-slate-400">The viewer uses the best sparse attempt by default, not necessarily the latest run.</p>
                </div>
                <Link href={`/projects/${params.id}/viewer`} className="rounded-md bg-brand px-3 py-2 text-sm font-semibold text-ink hover:bg-cyan-200">
                  View Best Attempt
                </Link>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                  <p className="text-xs text-slate-500">Best attempt</p>
                  <p className="mt-1 text-sm font-semibold text-white">{bestAttempt?.label ?? "Unavailable"}</p>
                </div>
                <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                  <p className="text-xs text-slate-500">Latest attempt</p>
                  <p className="mt-1 text-sm font-semibold text-white">{latestAttempt?.label ?? "Unavailable"}</p>
                </div>
              </div>
              <div className="mt-3 space-y-2">
                {attempts.map((attempt) => (
                  <div key={attempt.attemptId} className={`rounded-md border p-3 text-sm ${attempt.isBestAttempt ? "border-emerald-300/20 bg-emerald-300/10 text-emerald-100" : "border-white/10 bg-white/[0.03] text-slate-300"}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span>{attempt.label}</span>
                      <span className="text-xs">{attempt.isBestAttempt ? "Best attempt" : attempt.status}</span>
                    </div>
                    {attempt.failureReason && <p className="mt-1 text-xs text-red-100/80">{attempt.failureReason}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
          {sparseQualityPoor && (reconstruction?.registeredImageCount ?? 0) > 0 && (
            <div className="mt-4 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">
              Only {reconstruction?.registeredImageCount ?? 0} out of {reconstruction?.extractedFrameCount ?? reconstruction?.inputFrameCount ?? 0} frames were registered by COLMAP. This means most frames could not be matched reliably.
            </div>
          )}
          {(reconstruction?.warnings ?? []).length > 0 && (
            <div className="mt-4 space-y-2">
              {(reconstruction?.warnings ?? []).map((warning) => (
                <div key={warning} className="rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="glass-panel mt-6 rounded-lg p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Cpu size={18} className="text-brand" />
                <h2 className="text-lg font-semibold text-white">Dense Reconstruction</h2>
              </div>
              <p className="mt-2 max-w-2xl text-sm text-slate-400">
                Phase 3A runs COLMAP image undistortion, patch match stereo, and stereo fusion to produce a dense point cloud. It does not generate a mesh or GLB.
              </p>
            </div>
            {!denseLikelyUnavailable && !sparseQualityPoor && (
              <button
                disabled={!canRunDense || denseReconstructing}
                onClick={onRunDenseReconstruction}
                className="rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-ink hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {denseReconstructing ? "Running Dense Reconstruction..." : "Run Dense Reconstruction"}
              </button>
            )}
          </div>

          <div className="mt-4 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">
            {denseLikelyUnavailable ? "Dense reconstruction is unavailable with the current COLMAP build. Sparse reconstruction works, but dense stereo requires a CUDA-enabled COLMAP build." : "Dense reconstruction can take much longer than sparse reconstruction, especially without CUDA."}
          </div>

          <div className="mt-5 rounded-md border border-white/10 bg-slate-950/60 p-4">
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
                <p className="mt-1 text-sm font-semibold text-white">{sparseComplete ? "Complete" : "Incomplete"}</p>
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
              <p className="mt-3 text-xs text-amber-100">Dense reconstruction is not recommended yet: {denseReadiness?.reasons.join(", ")}.</p>
            )}
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-4">
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Sparse status</p>
              <p className="mt-2 text-sm font-semibold text-white">{reconstruction?.sparseStatus ?? reconstruction?.status ?? "Not Started"}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Dense status</p>
              <p className="mt-2 text-sm font-semibold text-white">{reconstruction?.denseStatus ?? "Dense Reconstruction Not Started"}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Sparse points</p>
              <p className="mt-2 text-2xl font-semibold text-white">{reconstruction?.sparsePointCount ?? reconstruction?.pointCount ?? 0}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Dense points</p>
              <p className="mt-2 text-2xl font-semibold text-white">{reconstruction?.densePointCount ?? 0}</p>
            </div>
          </div>

          {!sparseComplete && (
            <div className="mt-4 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">
              Run sparse reconstruction successfully before dense reconstruction.
            </div>
          )}
          {sparseQualityPoor && (
            <div className="mt-4 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">
              Dense reconstruction is not recommended because the sparse reconstruction is too weak.
            </div>
          )}
          {(denseLikelyUnavailable || sparseQualityPoor) && (
            <details className="mt-4 rounded-md border border-white/10 bg-white/[0.03] p-3">
              <summary className="cursor-pointer text-sm font-semibold text-slate-200">Advanced dense reconstruction action</summary>
              <button
                disabled={!canRunDense || denseReconstructing}
                onClick={onRunDenseReconstruction}
                className="mt-3 rounded-md border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {denseReconstructing ? "Running Dense Reconstruction..." : "Run Dense Reconstruction"}
              </button>
            </details>
          )}
          {(denseReconstructionError || reconstruction?.denseStatus === "Dense Reconstruction Failed") && (
            <div className="mt-4 rounded-md border border-red-400/30 bg-red-400/10 p-3 text-sm text-red-100">
              <p className="font-semibold">Dense reconstruction failed</p>
              <p className="mt-1">{reconstruction?.denseErrorMessage ?? denseReconstructionError}</p>
              {(reconstruction?.denseLikelyCauses ?? []).length > 0 && (
                <p className="mt-2 text-xs text-red-100/80">Likely causes: {(reconstruction?.denseLikelyCauses ?? []).join(", ")}.</p>
              )}
              {denseLogEntries.length > 0 && (
                <details className="mt-3">
                  <summary className="cursor-pointer text-xs font-semibold text-red-100/80">Technical details</summary>
                  <div className="mt-2 space-y-2">
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
          {reconstruction?.denseStatus === "Dense Reconstruction Complete" && (
            <div className="mt-4 rounded-md border border-emerald-300/20 bg-emerald-300/10 p-3 text-sm text-emerald-100">
              Dense point cloud complete. Mesh generation and GLB export are the next milestone.
            </div>
          )}
        </section>

        <section className="glass-panel mt-6 rounded-lg p-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white">Capture Review</h2>
              <p className="mt-1 text-sm text-slate-400">Preview thumbnails from the uploaded capture. Reconstruction uses the full extracted frames.</p>
            </div>
            <span className="text-sm text-slate-400">{frames.length} frame(s)</span>
          </div>
          {frames.length === 0 ? (
            <div className="mt-4 flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.03] p-5 text-sm text-slate-400">
              <ImageIcon size={18} />
              No extracted frames are available yet.
            </div>
          ) : (
            <>
            <div className="mt-4 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">
              Preview thumbnails are compressed for speed. Reconstruction uses the full extracted frames.
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              {selectedFrames.map((frame, index) => (
                <button key={`${frame.filename}-${index}`} type="button" onClick={() => setLargeFrame(frame)} className="overflow-hidden rounded-md border border-white/10 bg-slate-950 text-left">
                  <img src={`${API_BASE}${frame.thumbnailUrl}`} alt={frame.filename} className="h-36 w-full object-cover" />
                  <p className="px-2 py-2 text-xs text-slate-300">{index === 0 ? "First frame" : index === 1 ? "Middle frame" : "Last frame"}</p>
                </button>
              ))}
            </div>
            <details className="mt-4" open={showAllFrames} onToggle={(event) => setShowAllFrames(event.currentTarget.open)}>
              <summary className="cursor-pointer rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm font-semibold text-slate-200">
                Show all frames
              </summary>
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                {frames.map((frame) => (
                  <div key={frame.filename} className="overflow-hidden rounded-md border border-white/10 bg-slate-950">
                    <button type="button" onClick={() => setLargeFrame(frame)} className="block w-full">
                      <img src={`${API_BASE}${frame.thumbnailUrl}`} alt={frame.filename} className="h-28 w-full object-cover" />
                    </button>
                    <p className="truncate px-2 py-2 text-xs text-slate-400">{frame.filename}</p>
                  </div>
                ))}
              </div>
            </details>
            </>
          )}
        </section>
        {largeFrame && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-6" onClick={() => setLargeFrame(null)}>
            <div className="max-h-full max-w-5xl overflow-hidden rounded-lg border border-white/10 bg-slate-950" onClick={(event) => event.stopPropagation()}>
              <img src={`${API_BASE}${largeFrame.frameUrl}`} alt={largeFrame.filename} className="max-h-[80vh] w-full object-contain" />
              <div className="flex items-center justify-between px-4 py-3 text-sm text-slate-300">
                <span>{largeFrame.filename} full extracted reconstruction frame</span>
                <button type="button" onClick={() => setLargeFrame(null)} className="rounded-md border border-white/10 px-3 py-1.5 hover:bg-white/10">Close</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
