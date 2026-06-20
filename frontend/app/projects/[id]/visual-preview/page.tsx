"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { exportVisualPreview, getProject, getVisualPreviewDiagnostics, getVisualPreviewSplatMetadata, getVisualPreviewSummary, getVisualPreviewTrainingStatus, prepareVisualPreview, trainVisualPreview, visualPreviewSplatDownloadUrl } from "@/lib/api";
import type { Project, VisualPreviewDiagnostics, VisualPreviewPreset, VisualPreviewSplatMetadata, VisualPreviewSummary, VisualPreviewTrainingStatusResponse } from "@/lib/types";
import { ArrowLeft, CheckCircle2, Download, ExternalLink, FileJson, Loader2, XCircle } from "lucide-react";

const TRAINING_PRESETS: Array<{ value: VisualPreviewPreset; label: string; iterations: number }> = [
  { value: "smoke", label: "Smoke test, 1 iter", iterations: 1 },
  { value: "quick", label: "Quick preview, 1000 iters", iterations: 1000 },
  { value: "demo", label: "Demo quality, 7000 iters", iterations: 7000 },
  { value: "quality", label: "High quality, 30000 iters", iterations: 30000 }
];

export default function VisualPreviewPage() {
  const params = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [summary, setSummary] = useState<VisualPreviewSummary | null>(null);
  const [diagnostics, setDiagnostics] = useState<VisualPreviewDiagnostics | null>(null);
  const [training, setTraining] = useState<VisualPreviewTrainingStatusResponse | null>(null);
  const [splatMetadata, setSplatMetadata] = useState<VisualPreviewSplatMetadata | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [trainingNow, setTrainingNow] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [preset, setPreset] = useState<VisualPreviewPreset>("demo");
  const [error, setError] = useState("");

  useEffect(() => {
    getProject(params.id).then(setProject).catch(() => setProject(null));
    getVisualPreviewSummary(params.id).then(setSummary).catch(() => setSummary(null));
    getVisualPreviewDiagnostics().then(setDiagnostics).catch(() => setDiagnostics(null));
    getVisualPreviewTrainingStatus(params.id).then(setTraining).catch(() => setTraining(null));
  }, [params.id]);

  useEffect(() => {
    if (training?.trainingStatus !== "running" && training?.trainingStatus !== "queued" && training?.exportStatus !== "running") return;
    const timer = window.setTimeout(() => {
      getVisualPreviewTrainingStatus(params.id).then(setTraining).catch(() => undefined);
      getVisualPreviewSummary(params.id).then(setSummary).catch(() => undefined);
    }, 2500);
    return () => window.clearTimeout(timer);
  }, [params.id, training?.trainingStatus, training?.exportStatus, training?.recentTrainingLog]);

  useEffect(() => {
    const visualPreviewId = training?.visualPreviewId ?? summary?.visualPreview?.visualPreviewId;
    if (!visualPreviewId) {
      setSplatMetadata(null);
      return;
    }
    getVisualPreviewSplatMetadata(params.id, visualPreviewId).then(setSplatMetadata).catch(() => setSplatMetadata(null));
  }, [params.id, summary?.visualPreview?.visualPreviewId, training?.visualPreviewId, training?.splatOutputPath, training?.exportStatus]);

  async function onPrepare() {
    setPreparing(true);
    setError("");
    try {
      const next = await prepareVisualPreview(params.id);
      setSummary(next);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Visual preview preparation failed");
      getVisualPreviewSummary(params.id).then(setSummary).catch(() => undefined);
    } finally {
      setPreparing(false);
    }
  }

  async function onTrain() {
    setTrainingNow(true);
    setError("");
    try {
      const next = await trainVisualPreview(params.id, { visualPreviewId: manifest?.visualPreviewId, trainingPreset: preset });
      setTraining(next);
      getVisualPreviewSummary(params.id).then(setSummary).catch(() => undefined);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Visual preview training could not start");
      getVisualPreviewTrainingStatus(params.id).then(setTraining).catch(() => undefined);
    } finally {
      setTrainingNow(false);
    }
  }

  async function onExport() {
    setExporting(true);
    setError("");
    try {
      const next = await exportVisualPreview(params.id, manifest?.visualPreviewId);
      setTraining(next);
      getVisualPreviewSummary(params.id).then(setSummary).catch(() => undefined);
      getVisualPreviewSplatMetadata(params.id, next.visualPreviewId ?? manifest?.visualPreviewId).then(setSplatMetadata).catch(() => undefined);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Visual preview export failed");
      getVisualPreviewTrainingStatus(params.id).then(setTraining).catch(() => undefined);
    } finally {
      setExporting(false);
    }
  }

  const readiness = summary?.readiness;
  const manifest = summary?.visualPreview;
  const manifestDetails = (manifest?.summaryJson ?? {}) as Record<string, unknown>;
  const datasetReadiness = (manifestDetails.datasetReadiness ?? {}) as { ready?: boolean; missing?: string[]; imageCount?: number; imagesPath?: string; sparsePath?: string };
  const trainingStatus = training?.trainingStatus ?? manifest?.trainingStatus ?? "not_started";
  const exportStatus = training?.exportStatus ?? manifest?.exportStatus ?? "not_started";
  const trainingPreset = (training?.trainingPreset ?? training?.summaryJson?.trainingPreset ?? training?.summaryJson?.preset ?? manifest?.trainingPreset ?? manifestDetails.trainingPreset ?? manifestDetails.preset ?? preset) as string;
  const selectedPreset = TRAINING_PRESETS.find((item) => item.value === trainingPreset);
  const maxIterations = training?.maxIterations ?? (training?.summaryJson?.maxIterations as number | undefined) ?? manifest?.maxIterations ?? (manifestDetails.maxIterations as number | undefined) ?? selectedPreset?.iterations;
  const trainingBusy = trainingStatus === "running" || trainingStatus === "queued";
  const hasDatasetFailure = datasetReadiness.ready === false;
  const canTrain = Boolean(readiness?.ready && manifest && diagnostics?.nerfstudioAvailable && !hasDatasetFailure && !trainingBusy);
  const canExport = Boolean(diagnostics?.nerfstudioAvailable && (training?.nerfstudioConfigPath || manifest?.nerfstudioConfigPath) && exportStatus !== "running" && exportStatus !== "complete");
  const trainingCommand = ((training?.summaryJson?.trainingCommand ?? manifestDetails.trainingCommand) as string[] | undefined)?.join(" ");
  const exportCommand = ((training?.summaryJson?.exportCommand ?? manifestDetails.exportCommand) as string[] | undefined)?.join(" ");
  const trainingDuration = training?.summaryJson?.trainingDurationSeconds ?? manifestDetails.trainingDurationSeconds;
  const trainingDurationLabel = trainingDuration === undefined || trainingDuration === null ? null : String(trainingDuration);
  const splatSize = training?.splatOutputSizeBytes ?? manifest?.splatOutputSizeBytes ?? (manifestDetails.splatOutputSizeBytes as number | undefined);
  const exportedFileSize = splatMetadata?.fileSizeBytes ?? splatSize;
  const splatSizeLabel = typeof exportedFileSize === "number" ? `${(exportedFileSize / 1024 / 1024).toFixed(2)} MB` : "Unknown";
  const exportedPath = training?.splatOutputPath ?? manifest?.splatOutputPath ?? null;
  const exportedVisualPreviewId = splatMetadata?.visualPreviewId ?? training?.visualPreviewId ?? manifest?.visualPreviewId;
  const downloadUrl = splatMetadata?.exists && exportedVisualPreviewId ? visualPreviewSplatDownloadUrl(params.id, exportedVisualPreviewId) : null;

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <div className="flex flex-wrap items-center gap-3 text-sm text-slate-300">
          <Link href={`/projects/${params.id}/viewer`} className="inline-flex items-center gap-2 hover:text-white"><ArrowLeft size={16} /> Viewer</Link>
          <Link href={`/projects/${params.id}/model-artifacts`} className="rounded-md border border-brand/40 px-3 py-1.5 font-medium text-brand hover:bg-brand/10">Model Artifacts</Link>
          <Link href={`/projects/${params.id}/report`} className="hover:text-white">Report</Link>
        </div>

        <div className="glass-panel mt-5 rounded-lg p-8">
          <p className="text-sm text-amber-100">Legacy experimental preview</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">{project?.name ?? "Legacy preview"}</h1>
          <p className="mt-3 text-sm leading-6 text-slate-400">
            This Nerfstudio/Gaussian Splat experiment is retained for legacy records only. Use Model Artifacts and external photogrammetry outputs for the active product workflow.
          </p>

          <section className="mt-8 rounded-lg border border-white/10 bg-white/[0.03] p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="font-semibold text-white">Nerfstudio diagnostics</h2>
                <p className="mt-1 text-sm text-slate-400">{diagnostics?.recommendedSetupMessage ?? "Checking Nerfstudio setup..."}</p>
              </div>
              <span className={`rounded-md border px-2.5 py-1 text-xs font-semibold ${diagnostics?.nerfstudioAvailable ? "border-emerald-300/20 bg-emerald-300/10 text-emerald-100" : "border-amber-300/20 bg-amber-300/10 text-amber-100"}`}>
                {diagnostics?.nerfstudioAvailable ? "Available" : "Missing"}
              </span>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <div>
                <p className="text-xs text-slate-500">Python</p>
                <p className="mt-1 break-all text-xs text-slate-300">{diagnostics?.nerfstudioPython ?? "Not found"}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">ns-train</p>
                <p className="mt-1 break-all text-xs text-slate-300">{diagnostics?.nsTrainPath ?? "Not found"}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">ns-export</p>
                <p className="mt-1 break-all text-xs text-slate-300">{diagnostics?.nsExportPath ?? "Not found"}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">CUDA</p>
                <p className="mt-1 text-xs text-slate-300">{String(diagnostics?.cudaLikelyAvailable ?? "unknown")} {diagnostics?.torchCudaVersion ? `(${diagnostics.torchCudaVersion})` : ""}</p>
                {diagnostics?.cudaDeviceName && <p className="mt-1 text-xs text-slate-500">{diagnostics.cudaDeviceName}</p>}
              </div>
            </div>
            {!diagnostics?.nerfstudioAvailable && (
              <p className="mt-4 text-sm text-amber-100">Nerfstudio is not available on this machine. Install/configure Nerfstudio to train Gaussian Splat visual previews.</p>
            )}
            {(diagnostics?.warnings ?? []).length > 0 && (
              <ul className="mt-3 space-y-1 text-xs text-amber-100/85">
                {(diagnostics?.warnings ?? []).map((warning) => <li key={warning}>{warning}</li>)}
              </ul>
            )}
            {(diagnostics?.errors ?? []).length > 0 && (
              <ul className="mt-3 space-y-1 text-xs text-red-100/85">
                {(diagnostics?.errors ?? []).map((item) => <li key={item}>{item}</li>)}
              </ul>
            )}
          </section>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Status</p>
              <p className="mt-2 text-sm font-semibold text-white">{summary?.status ?? "not_started"}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Linked sparse attempt</p>
              <p className="mt-2 truncate text-sm font-semibold text-white">{summary?.sourceAttempt?.attemptId ?? manifest?.sourceAttemptId ?? "None"}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Readiness</p>
              <p className="mt-2 text-sm font-semibold text-white">{readiness?.label ?? "Not evaluated"}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Training</p>
              <p className="mt-2 text-sm font-semibold text-white">{trainingStatus}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Training preset</p>
              <p className="mt-2 text-sm font-semibold text-white">{selectedPreset?.label ?? trainingPreset ?? "Demo quality"}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Max iterations</p>
              <p className="mt-2 text-sm font-semibold text-white">{maxIterations ?? "7000"}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Export</p>
              <p className="mt-2 text-sm font-semibold text-white">{exportStatus}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Viewer asset</p>
              <p className="mt-2 break-all text-xs font-semibold text-white">{training?.viewerAssetPath ?? manifest?.viewerAssetPath ?? "Not exported"}</p>
            </div>
          </div>

          <section className="mt-8">
            <h2 className="font-semibold text-white">Readiness checks</h2>
            <div className="mt-3 space-y-3">
              {(readiness?.checks ?? []).map((check) => (
                <div key={check.key} className={`flex items-start gap-3 rounded-md border p-3 text-sm ${check.passed ? "border-emerald-300/20 bg-emerald-300/10 text-emerald-100" : "border-amber-300/20 bg-amber-300/10 text-amber-100"}`}>
                  {check.passed ? <CheckCircle2 size={17} className="mt-0.5 shrink-0" /> : <XCircle size={17} className="mt-0.5 shrink-0" />}
                  <div>
                    <p className="font-semibold">{check.label}</p>
                    {!check.passed && <p className="mt-1 text-xs opacity-85">{check.detail}</p>}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {manifest ? (
            <section className="mt-8">
              <h2 className="font-semibold text-white">Generated manifest</h2>
              <div className="mt-3 rounded-lg border border-emerald-300/20 bg-emerald-300/10 p-4 text-sm text-emerald-50">
                <div className="flex items-start gap-3">
                  <FileJson size={18} className="mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <p className="font-semibold">Visual Preview manifest ready</p>
                    <p className="mt-1 break-all text-xs text-emerald-50/85">{manifest.manifestPath}</p>
                  </div>
                </div>
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                  <p className="text-xs text-slate-500">Registered images</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{String(manifestDetails.registeredImageCount ?? readiness?.registeredImageCount ?? 0)}</p>
                </div>
                <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                  <p className="text-xs text-slate-500">Sparse points</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{String(manifestDetails.sparsePointCount ?? readiness?.sparsePointCount ?? 0)}</p>
                </div>
              </div>
              <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300">
                <p className="break-all">Image folder: {String(manifestDetails.imageFolderPath ?? readiness?.imageFolderPath ?? "Not available")}</p>
                <p className="mt-2 break-all">COLMAP model: {String(manifestDetails.colmapModelPath ?? readiness?.colmapModelPath ?? "Not available")}</p>
                <p className="mt-2 break-all">Nerfstudio dataset: {String(manifestDetails.nerfstudioDatasetPath ?? "Created when training starts")}</p>
                <p className="mt-2">Dataset images: {String(datasetReadiness.imageCount ?? manifestDetails.nerfstudioDatasetImageCount ?? "Created when training starts")}</p>
                {hasDatasetFailure && <p className="mt-2 text-amber-100">Missing dataset files: {(datasetReadiness.missing ?? []).join(", ")}</p>}
              </div>
            </section>
          ) : (
            <section className="mt-8 rounded-lg border border-white/10 bg-white/[0.03] p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="font-semibold text-white">No manifest prepared</h2>
                  <p className="mt-1 text-sm text-slate-400">Prepare visual preview inputs from the best sparse attempt.</p>
                </div>
                <button
                  type="button"
                  disabled={!readiness?.ready || preparing}
                  onClick={onPrepare}
                  className="inline-flex items-center gap-2 rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-ink hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {preparing && <Loader2 size={16} className="animate-spin" />}
                  Prepare Visual Preview
                </button>
              </div>
              {error && <p className="mt-3 text-sm text-red-100">{error}</p>}
              {(readiness?.reasons ?? []).length > 0 && (
                <p className="mt-3 text-sm text-amber-100">Not recommended yet: {readiness?.reasons.join(" ")}</p>
              )}
            </section>
          )}

          {manifest && (
            <section className="mt-8 rounded-lg border border-white/10 bg-white/[0.03] p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="font-semibold text-white">Train and export</h2>
                  <p className="mt-1 text-sm text-slate-400">This launches Nerfstudio Splatfacto as an external subprocess and returns immediately.</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <select
                    value={preset}
                    disabled={trainingBusy}
                    onChange={(event) => setPreset(event.target.value as VisualPreviewPreset)}
                    className="rounded-md border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {TRAINING_PRESETS.map((item) => (
                      <option key={item.value} value={item.value}>{item.label}</option>
                    ))}
                  </select>
                  <button type="button" disabled={!canTrain || trainingNow} onClick={onTrain} className="inline-flex items-center gap-2 rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-ink hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50">
                    {trainingNow && <Loader2 size={16} className="animate-spin" />}
                    Train Visual Preview
                  </button>
                  <button type="button" disabled={!canExport || exporting} onClick={onExport} className="inline-flex items-center gap-2 rounded-md border border-white/10 px-4 py-2.5 text-sm font-semibold text-slate-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50">
                    {exporting && <Loader2 size={16} className="animate-spin" />}
                    Export Gaussian Splat
                  </button>
                </div>
              </div>
              <p className="mt-3 text-sm text-slate-400">Smoke only validates the pipeline. Demo or Quality are required for meaningful visual output.</p>
              {training?.nerfstudioConfigPath && <p className="mt-3 break-all text-xs text-slate-400">Config: {training.nerfstudioConfigPath}</p>}
              <p className="mt-3 text-xs text-slate-400">Selected preset: {selectedPreset?.label ?? trainingPreset}. Max iterations: {maxIterations ?? "7000"}.</p>
              {trainingCommand && <p className="mt-3 break-all text-xs text-slate-400">Train command: {trainingCommand}</p>}
              {exportCommand && <p className="mt-2 break-all text-xs text-slate-400">Export command: {exportCommand}</p>}
              {trainingDurationLabel && <p className="mt-2 text-xs text-slate-400">Duration: {trainingDurationLabel} seconds</p>}
              {trainingStatus === "complete" && exportStatus !== "complete" && exportStatus !== "running" && (
                <p className="mt-3 text-sm text-slate-300">Training is complete. Export the Gaussian Splat `.ply` to open it in an external viewer.</p>
              )}
              {exportStatus === "failed" && (
                <p className="mt-3 text-sm text-red-100">{training?.errorMessage ?? manifest?.errorMessage ?? "Gaussian Splat export failed."}</p>
              )}
              {error && <p className="mt-3 text-sm text-red-100">{error}</p>}
            </section>
          )}

          {(splatMetadata?.exists || exportStatus === "complete" || exportedPath) && (
            <section className="mt-8 rounded-lg border border-emerald-300/20 bg-emerald-300/10 p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="font-semibold text-white">Gaussian Splat exported successfully.</h2>
                  <p className="mt-1 text-sm text-emerald-50/85">This is a real Nerfstudio/Splatfacto `.ply` export from the selected sparse reconstruction.</p>
                </div>
                {downloadUrl && (
                  <a
                    href={downloadUrl}
                    className="inline-flex items-center gap-2 rounded-md bg-emerald-200 px-4 py-2.5 text-sm font-semibold text-emerald-950 hover:bg-emerald-100"
                  >
                    <Download size={16} />
                    Download .ply
                  </a>
                )}
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-3">
                <div>
                  <p className="text-xs text-emerald-100/70">File name</p>
                  <p className="mt-1 break-all text-sm font-semibold text-white">{splatMetadata?.fileName ?? "splat.ply"}</p>
                </div>
                <div>
                  <p className="text-xs text-emerald-100/70">File size</p>
                  <p className="mt-1 text-sm font-semibold text-white">{splatSizeLabel}</p>
                </div>
                <div>
                  <p className="text-xs text-emerald-100/70">Relative path</p>
                  <p className="mt-1 break-all text-sm font-semibold text-white">{splatMetadata?.relativePath ?? "exports\\splat.ply"}</p>
                </div>
              </div>
              <p className="mt-4 break-all text-xs text-emerald-50/80">Export path: {exportedPath ?? training?.viewerAssetPath ?? manifest?.viewerAssetPath ?? "Stored in project visual preview exports."}</p>
            </section>
          )}

          {(splatMetadata?.exists || exportStatus === "complete" || exportedPath) && (
            <section className="mt-8 rounded-lg border border-white/10 bg-white/[0.03] p-5">
              <div className="flex items-start gap-3">
                <ExternalLink size={18} className="mt-0.5 shrink-0 text-brand" />
                <div>
                  <h2 className="font-semibold text-white">Open in External Viewer</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    Browser rendering inside Structura is pending. Download the exported `.ply` and open it in a compatible Gaussian Splat viewer such as SuperSplat or Polycam.
                  </p>
                </div>
              </div>
            </section>
          )}

          <section className="mt-8 rounded-lg border border-white/10 bg-slate-950/70 p-5">
            <h2 className="font-semibold text-white">Recent logs</h2>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div>
                <p className="text-xs font-semibold text-slate-300">Training</p>
                <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-md border border-white/10 bg-black/30 p-3 text-xs leading-5 text-slate-300">{training?.recentTrainingLog || "No training logs yet."}</pre>
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-300">Export</p>
                <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-md border border-white/10 bg-black/30 p-3 text-xs leading-5 text-slate-300">{training?.recentExportLog || "No export logs yet."}</pre>
              </div>
            </div>
          </section>

          <div className="mt-8 rounded-lg border border-white/10 bg-slate-950/60 p-4 text-sm text-slate-300">
            Visual preview is optimized for viewing, not measurement-grade geometry.
          </div>
        </div>
      </div>
    </AppShell>
  );
}
