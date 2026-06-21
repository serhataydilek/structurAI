"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Download, ExternalLink, Loader2, Play, TriangleAlert } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { RealityScanModelViewer } from "@/components/RealityScanModelViewer";
import { getCaptureSummary, getModelPreviewDiagnostics, getModelPreviewStatus, getProcessingStatus, getRealityScanDiagnostics, getRealityScanStatus, listModelArtifacts, modelArtifactDownloadUrl, prepareModelPreview, runRealityScanModel } from "@/lib/api";
import type { CaptureSummary, ModelArtifact, ModelPreviewDiagnostics, ModelPreviewStatus, ProcessingStatus, RealityScanDiagnostics, RealityScanStatus } from "@/lib/types";

const ACTIVE_STATUSES = new Set(["preparing", "running", "importing"]);
const MINIMUM_VALIDATED_IMAGES = 20;
const VIEWER_FORMATS = new Set(["glb", "gltf"]);

function formatDuration(seconds: number | null) {
  if (seconds === null || seconds === undefined) return "--";
  const rounded = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(rounded / 60);
  return minutes ? `${minutes}m ${rounded % 60}s` : `${rounded}s`;
}

function modelFormat(artifact: ModelArtifact | null | undefined) {
  return (artifact?.format ?? artifact?.bundle?.mainGlbPath?.split(".").pop() ?? artifact?.bundle?.mainObjPath?.split(".").pop() ?? artifact?.fileName.split(".").pop() ?? "").toLowerCase();
}

function isRawRealityScanObjBundle(artifact: ModelArtifact) {
  return artifact.source_type === "realityscan" && artifact.status === "ready" && artifact.artifactRole === "raw_realityscan" && modelFormat(artifact) === "obj";
}

export default function PhotogrammetryPage() {
  const { id } = useParams<{ id: string }>();
  const [diagnostics, setDiagnostics] = useState<RealityScanDiagnostics | null>(null);
  const [processing, setProcessing] = useState<ProcessingStatus | null>(null);
  const [capture, setCapture] = useState<CaptureSummary | null>(null);
  const [job, setJob] = useState<RealityScanStatus | null>(null);
  const [artifact, setArtifact] = useState<ModelArtifact | null>(null);
  const [rawArtifact, setRawArtifact] = useState<ModelArtifact | null>(null);
  const [viewerArtifact, setViewerArtifact] = useState<ModelArtifact | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const [previewDiagnostics, setPreviewDiagnostics] = useState<ModelPreviewDiagnostics | null>(null);
  const [previewStatus, setPreviewStatus] = useState<ModelPreviewStatus | null>(null);
  const [preparingPreview, setPreparingPreview] = useState(false);
  const [viewerVisible, setViewerVisible] = useState(false);

  const load = async () => {
    const [nextDiagnostics, nextProcessing, nextCapture, nextJob, artifactSummary] = await Promise.all([
      getRealityScanDiagnostics().catch(() => null),
      getProcessingStatus(id).catch(() => null),
      getCaptureSummary(id).catch(() => null),
      getRealityScanStatus(id).catch(() => null),
      listModelArtifacts(id).catch(() => null),
    ]);
    setDiagnostics(nextDiagnostics);
    setProcessing(nextProcessing);
    setCapture(nextCapture);
    setJob(nextJob);
    getModelPreviewDiagnostics().then(setPreviewDiagnostics).catch(() => setPreviewDiagnostics(null));
    const artifacts = artifactSummary?.artifacts ?? [];
    const readyRealityScanArtifacts = artifacts.filter((item) => item.source_type === "realityscan" && item.status === "ready");
    const nextRawArtifact = readyRealityScanArtifacts.find(isRawRealityScanObjBundle)
      ?? readyRealityScanArtifacts.find((item) => modelFormat(item) === "obj")
      ?? null;
    const preferred = artifactSummary?.preferredModelArtifact ?? null;
    const nextViewerArtifact = artifacts.find((item) => item.artifactRole === "viewer_ready" && item.status === "ready" && VIEWER_FORMATS.has(modelFormat(item)))
      ?? (preferred?.artifactRole === "viewer_ready" && VIEWER_FORMATS.has(modelFormat(preferred)) ? preferred : null);
    const artifactForLatestJob = nextViewerArtifact ?? (nextJob?.status === "completed"
      ? readyRealityScanArtifacts.find((item) => item.job_id === nextJob.job_id) ?? nextRawArtifact
      : nextRawArtifact);
    setRawArtifact(nextRawArtifact);
    setViewerArtifact(nextViewerArtifact);
    setArtifact(artifactForLatestJob);
  };

  useEffect(() => {
    load().catch(() => setError("Unable to load the photogrammetry workflow"));
  }, [id]);

  const jobIsActive = Boolean(job && ACTIVE_STATUSES.has(job.status));
  const captureProcessingActive = processing?.status === "Processing" || processing?.jobProgress?.status === "running";
  const captureReady = !captureProcessingActive && Boolean(processing?.workspacePrepared && capture?.workspacePrepared);
  const validatedImageCount = capture?.extractedFrameCount ?? processing?.extractedFrameCount ?? 0;
  const hasEnoughValidatedImages = captureReady && validatedImageCount >= MINIMUM_VALIDATED_IMAGES;
  const realityScanRunning = busy || jobIsActive;
  const realityScanCompleted = job?.status === "completed";
  const hasReadyModelArtifact = Boolean(artifact);
  const rawArtifactFormat = modelFormat(rawArtifact);
  const viewerReadyAvailable = Boolean(viewerArtifact);
  const rawAvailable = Boolean(rawArtifact);
  const previewEnabled = Boolean(previewDiagnostics?.available && previewDiagnostics.enabled);
  const previewRunning = preparingPreview || previewStatus?.status === "running";
  const previewFailed = previewStatus?.status === "failed";
  const previewPercent = previewStatus?.progress_percent ?? previewStatus?.progress ?? null;
  const previewUnavailable = rawAvailable && !viewerReadyAvailable && previewDiagnostics !== null && !previewEnabled;
  const showViewer = Boolean(viewerArtifact && viewerVisible);
  const diagnosticsReady = Boolean(diagnostics?.enabled && diagnostics.executable_exists && diagnostics.export_params_exists);
  const realityScanCanRun = !captureProcessingActive && captureReady && hasEnoughValidatedImages && diagnosticsReady && !realityScanRunning;
  const disabledReason = captureProcessingActive
    ? "Waiting for capture processing to finish."
    : !captureReady
      ? "Waiting for validated images."
      : !hasEnoughValidatedImages
        ? "At least 20 validated images are required."
        : !diagnostics?.executable_exists
          ? "RealityScan executable is not configured."
          : !diagnosticsReady
            ? "RealityScan executable is not configured."
            : realityScanRunning
              ? "RealityScan is already running."
              : null;

  useEffect(() => {
    if (!captureProcessingActive && !jobIsActive) return;
    const interval = window.setInterval(() => { load().catch(() => undefined); }, 2000);
    return () => window.clearInterval(interval);
  }, [captureProcessingActive, jobIsActive, id]);

  useEffect(() => {
    if (!jobIsActive || !job?.started_at) return;
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, [jobIsActive, job?.started_at]);

  const elapsedSeconds = useMemo(() => {
    if (job?.started_at && jobIsActive) {
      const started = Date.parse(job.started_at);
      if (!Number.isNaN(started)) return Math.max(0, Math.floor((now - started) / 1000));
    }
    return job?.elapsed_seconds ?? null;
  }, [job?.started_at, job?.elapsed_seconds, jobIsActive, now]);

  const showPreviewViewer = useCallback(() => {
    if (!viewerArtifact) return;
    setViewerVisible(true);
    window.setTimeout(() => document.getElementById("model-viewer")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  }, [viewerArtifact]);

  useEffect(() => {
    if (!rawArtifact || !previewRunning) return;
    let active = true;
    const poll = async () => {
      const status = await getModelPreviewStatus(id, rawArtifact.artifactId).catch(() => null);
      if (!active || !status) return;
      setPreviewStatus(status);
      if (status.status === "completed") {
        setPreparingPreview(false);
        await load().catch(() => undefined);
        setViewerVisible(true);
        window.setTimeout(() => document.getElementById("model-viewer")?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
        return;
      }
      if (status.status === "failed") {
        setPreparingPreview(false);
        return;
      }
      window.setTimeout(() => { if (active) poll().catch(() => undefined); }, 1500);
    };
    poll().catch(() => undefined);
    return () => { active = false; };
  }, [id, rawArtifact?.artifactId, previewRunning]);

  async function generate() {
    if (!realityScanCanRun) return;
    setBusy(true);
    setError("");
    setArtifact(null);
    setRawArtifact(null);
    setViewerArtifact(null);
    setViewerVisible(false);
    setPreviewStatus(null);
    try {
      const started = await runRealityScanModel(id);
      setJob({
        job_id: started.job_id, status: started.status as RealityScanStatus["status"], stage: "launching_realityscan",
        stage_key: "launching_realityscan", stage_label: "Launching RealityScan", progress: 0, progress_percent: 0,
        elapsed_seconds: null, eta_seconds: null, image_count: started.image_count, error_message: null,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "RealityScan model generation failed to start");
      load().catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  async function preparePreview() {
    if (!rawArtifact || previewRunning || (!previewEnabled && !previewFailed)) return;
    setPreparingPreview(true);
    setPreviewStatus({ status: "running", source_artifact_id: rawArtifact.artifactId, stage: "queued", progress: 5, progress_percent: 5, error_message: null });
    try {
      const status = await prepareModelPreview(id, rawArtifact.artifactId);
      setPreviewStatus(status);
    } catch (reason) {
      setPreviewStatus({ status: "failed", source_artifact_id: rawArtifact.artifactId, error_message: reason instanceof Error ? reason.message : "Preview preparation failed" });
      setPreparingPreview(false);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <div className="flex flex-wrap gap-4 text-sm text-slate-300">
          <Link href={`/projects/${id}/processing`} className="hover:text-white">Capture processing</Link>
          <Link href={`/projects/${id}/model-artifacts`} className="hover:text-white">Open Artifacts</Link>
          <Link href={`/projects/${id}/report`} className="hover:text-white">Report</Link>
        </div>

        <section className="mt-5 border border-white/10 bg-panel p-7 shadow-glow">
          <p className="text-sm text-brand">Upload / Capture Processing</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">Prepare validated images</h1>
          <p className="mt-3 text-sm text-slate-400">Media processing extracts frames, validates the image set, and prepares RealityScan input.</p>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <div><p className="text-xs text-slate-500">Status</p><p className="mt-1 font-semibold text-white">{captureProcessingActive ? "Processing capture" : captureReady ? "Capture ready" : "Awaiting capture"}</p></div>
            <div><p className="text-xs text-slate-500">Validated images</p><p className="mt-1 font-semibold text-white">{validatedImageCount}</p></div>
            <div><p className="text-xs text-slate-500">Requirement</p><p className="mt-1 font-semibold text-white">{MINIMUM_VALIDATED_IMAGES}+ images</p></div>
          </div>
          {!captureReady && <Link href={`/projects/${id}/processing`} className="mt-5 inline-flex rounded border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10">Open Capture Processing</Link>}
        </section>

        {hasReadyModelArtifact && (
          <section className="mt-6 border border-brand/40 bg-panel p-6 shadow-glow">
            <p className="text-sm text-brand">Production result</p><h2 className="mt-1 text-2xl font-semibold text-white">RealityScan model ready</h2>
            <p className="mt-2 text-sm text-slate-400">{viewerReadyAvailable ? "A viewer-ready 3D preview is available for this RealityScan model." : "Raw RealityScan OBJ is ready. Prepare a viewer-ready GLB to inspect it in the browser."}</p>
            {viewerReadyAvailable && <p className="mt-2 text-xs text-cyan-100">Preview optimized for web{typeof viewerArtifact?.stats?.faceCount === "number" ? ` - ${viewerArtifact.stats.faceCount.toLocaleString()} faces` : ""}</p>}
            <div className="mt-5 flex flex-wrap gap-3">
              {viewerReadyAvailable ? (
                <button onClick={showPreviewViewer} className="inline-flex items-center gap-2 rounded bg-brand px-3 py-2 text-sm font-medium text-ink"><ExternalLink size={16} />View 3D Preview</button>
              ) : (
                <button disabled={!previewDiagnostics || previewUnavailable || previewRunning} onClick={preparePreview} className="inline-flex items-center gap-2 rounded bg-brand px-3 py-2 text-sm font-medium text-ink disabled:cursor-not-allowed disabled:opacity-50">
                  {previewRunning && <Loader2 size={16} className="animate-spin" />}
                  {previewRunning ? `Preparing 3D Preview${previewPercent != null ? `... ${Math.round(previewPercent)}%` : "..."}` : previewFailed ? "Retry 3D Preview" : "Prepare 3D Preview"}
                </button>
              )}
              {rawArtifact && <a href={modelArtifactDownloadUrl(id, rawArtifact.artifactId)} className="inline-flex items-center gap-2 rounded border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10"><Download size={16} />{rawArtifactFormat === "obj" ? "Download Raw OBJ" : "Download Raw Model"}</a>}
              <Link href={`/projects/${id}/model-artifacts`} className="inline-flex items-center gap-2 rounded border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10"><ExternalLink size={16} />Open Artifact Details</Link>
            </div>
            {!viewerReadyAvailable && previewUnavailable && <p className="mt-3 text-xs text-amber-100">Preview preparation requires Blender configuration.</p>}
            {previewRunning && <div className="mt-4 max-w-md"><div className="h-2 overflow-hidden rounded-full bg-slate-800"><div className={`h-full bg-brand ${previewPercent == null ? "w-1/3 animate-pulse" : ""}`} style={previewPercent != null ? { width: `${Math.max(5, Math.min(100, previewPercent))}%` } : undefined} /></div><p className="mt-2 text-xs text-slate-400">{previewStatus?.stage ? previewStatus.stage.replaceAll("_", " ") : "Preparing preview"}{previewPercent != null ? ` - ${Math.round(previewPercent)}%` : ""}</p></div>}
            {previewFailed && <p className="mt-3 text-sm text-red-200">{previewStatus?.error_message ?? "Preview preparation failed."}</p>}
          </section>
        )}

        {!hasReadyModelArtifact && <section className="mt-6 border border-white/10 bg-panel p-7">
          <p className="text-sm text-brand">RealityScan Model Generation</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">Generate the production model</h2>
          <p className="mt-3 text-sm text-slate-400">RealityScan is the primary production model path. It starts only after capture processing and image validation are complete.</p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button disabled={!realityScanCanRun} onClick={generate} className="inline-flex items-center gap-2 rounded bg-brand px-4 py-2 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50">
              {realityScanRunning ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
              {busy ? "Preparing RealityScan..." : realityScanRunning ? "RealityScan is running" : "Generate RealityScan Model"}
            </button>
            {disabledReason && <span className="inline-flex items-center gap-2 text-sm text-amber-100"><TriangleAlert size={16} />{disabledReason}</span>}
          </div>
          {error && <p className="mt-4 text-sm text-red-200">{error}</p>}
        </section>}

        {(busy || (job && (ACTIVE_STATUSES.has(job.status) || ((job.status === "failed" || job.status === "cancelled") && !hasReadyModelArtifact)))) && (
          <section className="mt-6 border border-white/10 bg-panelSoft p-6">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-medium uppercase text-slate-400">RealityScan Model Generation</p><h2 className="mt-1 text-xl font-semibold text-white">{busy && !job ? "Preparing model generation" : job?.stage_label ?? "Waiting for RealityScan"}</h2><p className="mt-1 text-sm text-slate-400">{job?.status === "importing" ? "RealityScan finished, importing model artifact..." : "Overall progress across RealityScan stages"}</p></div><div className="text-right"><p className="text-2xl font-semibold text-brand">{job?.progress_percent ?? 0}%</p><p className="text-xs text-slate-400">Progress</p></div></div>
            <div className="mt-5 h-2 overflow-hidden bg-slate-800" aria-label="RealityScan progress"><div className={`h-full bg-brand transition-all ${busy && !job ? "animate-pulse" : ""}`} style={{ width: `${job?.progress_percent ?? 0}%` }} /></div>
            <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 text-sm sm:grid-cols-4"><div><dt className="text-slate-500">Elapsed</dt><dd className="mt-1 text-slate-100">{formatDuration(elapsedSeconds)}</dd></div><div><dt className="text-slate-500">ETA</dt><dd className="mt-1 text-slate-100">{job?.stable_eta_seconds != null ? `~${formatDuration(job.stable_eta_seconds)}` : "Estimating..."}</dd></div><div><dt className="text-slate-500">Images</dt><dd className="mt-1 text-slate-100">{job?.image_count ?? "--"}</dd></div><div><dt className="text-slate-500">Project</dt><dd className="mt-1 truncate text-slate-100">{job?.project_name ?? "Current project"}</dd></div></dl>
            {job?.error_message && <p className="mt-5 border-l-2 border-red-300 pl-3 text-sm text-red-200">{job.error_message}</p>}
          </section>
        )}

        {realityScanCompleted && !hasReadyModelArtifact && <section className="mt-6 border border-amber-300/30 bg-amber-300/10 p-4"><p className="font-semibold text-amber-50">RealityScan completed but no ready model artifact was found.</p><p className="mt-1 text-sm text-amber-100/80">Check the RealityScan export and Open Artifacts before treating this model as ready.</p></section>}

        {showViewer && viewerArtifact && (
          <section id="model-viewer" className="mt-6 border border-brand/30 bg-panel p-6 shadow-glow"><p className="text-sm text-brand">3D preview</p><h2 className="mt-1 text-2xl font-semibold text-white">Viewer-ready model</h2><p className="mt-1 text-sm text-slate-400">{viewerArtifact.fileName}</p><div className="mt-5"><RealityScanModelViewer artifact={viewerArtifact} projectId={id} /></div></section>
        )}

        <section className="mt-8 border-t border-white/10 pt-6"><p className="text-sm text-slate-400">Optional Validation &amp; Comparison</p><h2 className="mt-1 text-xl font-semibold text-white">Validate coverage or compare model states</h2><p className="mt-2 text-sm text-slate-400">Use COLMAP only to validate image coverage and alignment. RealityScan remains the production model path.</p><div className="mt-4 flex flex-wrap gap-3"><Link href={`/projects/${id}/processing#optional-validation`} className="rounded border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10">Run Optional Validation</Link>{hasReadyModelArtifact && <Link href={`/projects/${id}/model-artifacts#comparison`} className="rounded border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10">Open Comparison Tools</Link>}<Link href={`/projects/${id}/visual-preview`} className="rounded border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10">Experimental Visual Preview</Link></div></section>
      </div>
    </AppShell>
  );
}
