"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Download, ExternalLink, Loader2, Play, TriangleAlert } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { RealityScanModelViewer } from "@/components/RealityScanModelViewer";
import { getCaptureSummary, getProcessingStatus, getRealityScanDiagnostics, getRealityScanStatus, listModelArtifacts, modelArtifactDownloadUrl, runRealityScanModel } from "@/lib/api";
import type { CaptureSummary, ModelArtifact, ProcessingStatus, RealityScanDiagnostics, RealityScanStatus } from "@/lib/types";

const ACTIVE_STATUSES = new Set(["preparing", "running", "importing"]);
const MINIMUM_VALIDATED_IMAGES = 20;

function formatDuration(seconds: number | null) {
  if (seconds === null || seconds === undefined) return "--";
  const rounded = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(rounded / 60);
  return minutes ? `${minutes}m ${rounded % 60}s` : `${rounded}s`;
}

export default function PhotogrammetryPage() {
  const { id } = useParams<{ id: string }>();
  const [diagnostics, setDiagnostics] = useState<RealityScanDiagnostics | null>(null);
  const [processing, setProcessing] = useState<ProcessingStatus | null>(null);
  const [capture, setCapture] = useState<CaptureSummary | null>(null);
  const [job, setJob] = useState<RealityScanStatus | null>(null);
  const [artifact, setArtifact] = useState<ModelArtifact | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [now, setNow] = useState(() => Date.now());

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
    const readyRealityScanArtifacts = artifactSummary?.artifacts.filter((item) => item.source_type === "realityscan" && item.status === "ready") ?? [];
    const artifactForLatestJob = artifactSummary?.preferredModelArtifact ?? (nextJob?.status === "completed"
      ? readyRealityScanArtifacts.find((item) => item.job_id === nextJob.job_id) ?? null
      : readyRealityScanArtifacts[0] ?? null);
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

  async function generate() {
    if (!realityScanCanRun) return;
    setBusy(true);
    setError("");
    setArtifact(null);
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

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <div className="flex flex-wrap gap-4 text-sm text-slate-300">
          <Link href={`/projects/${id}/processing`} className="hover:text-white">Capture processing</Link>
          <Link href={`/projects/${id}/model-artifacts`} className="hover:text-white">Model Artifacts</Link>
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

        <section className="mt-6 border border-white/10 bg-panel p-7">
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
        </section>

        {(busy || job) && (
          <section className="mt-6 border border-white/10 bg-panelSoft p-6">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-medium uppercase text-slate-400">RealityScan Model Generation</p><h2 className="mt-1 text-xl font-semibold text-white">{busy && !job ? "Preparing model generation" : job?.stage_label ?? "Waiting for RealityScan"}</h2><p className="mt-1 text-sm text-slate-400">{job?.status === "importing" ? "RealityScan finished, importing model artifact..." : "Overall progress across RealityScan stages"}</p></div><div className="text-right"><p className="text-2xl font-semibold text-brand">{job?.progress_percent ?? 0}%</p><p className="text-xs text-slate-400">Progress</p></div></div>
            <div className="mt-5 h-2 overflow-hidden bg-slate-800" aria-label="RealityScan progress"><div className={`h-full bg-brand transition-all ${busy && !job ? "animate-pulse" : ""}`} style={{ width: `${job?.progress_percent ?? 0}%` }} /></div>
            <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 text-sm sm:grid-cols-4"><div><dt className="text-slate-500">Elapsed</dt><dd className="mt-1 text-slate-100">{formatDuration(elapsedSeconds)}</dd></div><div><dt className="text-slate-500">ETA</dt><dd className="mt-1 text-slate-100">{job?.stable_eta_seconds != null ? `~${formatDuration(job.stable_eta_seconds)}` : "Estimating..."}</dd></div><div><dt className="text-slate-500">Images</dt><dd className="mt-1 text-slate-100">{job?.image_count ?? "--"}</dd></div><div><dt className="text-slate-500">Project</dt><dd className="mt-1 truncate text-slate-100">{job?.project_name ?? "Current project"}</dd></div></dl>
            {job?.error_message && <p className="mt-5 border-l-2 border-red-300 pl-3 text-sm text-red-200">{job.error_message}</p>}
          </section>
        )}

        {realityScanCompleted && !hasReadyModelArtifact && <section className="mt-6 border border-amber-300/30 bg-amber-300/10 p-6"><p className="font-semibold text-amber-50">RealityScan completed but no model artifact was found.</p><p className="mt-1 text-sm text-amber-100/80">Check the RealityScan export and Model Artifacts before treating this model as ready.</p></section>}

        {hasReadyModelArtifact && (
          <section id="model-viewer" className="mt-6 border border-brand/30 bg-panel p-6 shadow-glow"><p className="text-sm text-brand">Primary result</p><h2 className="mt-1 text-2xl font-semibold text-white">3D Model Ready</h2><p className="mt-1 text-sm text-slate-400">RealityScan generated the production model artifact: {artifact?.fileName} {artifact?.bundle?.textureCount ? `with ${artifact.bundle.textureCount} textures` : ""}</p><div className="mt-5"><RealityScanModelViewer artifact={artifact!} projectId={id} /></div><div className="mt-5 flex flex-wrap gap-3"><a href="#model-viewer" className="inline-flex items-center gap-2 rounded bg-brand px-3 py-2 text-sm font-medium text-ink"><ExternalLink size={16} />View 3D Model</a><a href={modelArtifactDownloadUrl(id, artifact!.artifactId)} className="inline-flex items-center gap-2 rounded border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10"><Download size={16} />Download OBJ</a><Link href={`/projects/${id}/model-artifacts`} className="inline-flex items-center gap-2 rounded border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10"><ExternalLink size={16} />Open Model Artifact</Link></div></section>
        )}

        <section className="mt-8 border-t border-white/10 pt-6"><p className="text-sm text-slate-400">Optional Validation &amp; Comparison</p><h2 className="mt-1 text-xl font-semibold text-white">Validate capture or compare model states</h2><p className="mt-2 text-sm text-slate-400">COLMAP is optional validation only. Gaussian/Splatfacto remains an Experimental Visual Preview and is not a production reconstruction or cleanup path.</p><div className="mt-4 flex flex-wrap gap-3"><Link href={`/projects/${id}/processing`} className="rounded border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10">Open Optional Validation</Link><Link href={`/projects/${id}/model-artifacts`} className="rounded border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10">Open Comparison Tools</Link><Link href={`/projects/${id}/visual-preview`} className="rounded border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10">Experimental Visual Preview</Link></div></section>
      </div>
    </AppShell>
  );
}
