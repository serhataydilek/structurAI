"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { JobProgressCard } from "@/components/JobProgressCard";
import { getJobStatus, getRealityScanDiagnostics, listRealityScanJobs, prepareRealityScanJob } from "@/lib/api";
import type { JobProgress, PhotogrammetryJob, RealityScanDiagnostics } from "@/lib/types";

export default function PhotogrammetryPage() {
  const { id } = useParams<{ id: string }>();
  const [diag, setDiag] = useState<RealityScanDiagnostics | null>(null);
  const [jobs, setJobs] = useState<PhotogrammetryJob[]>([]);
  const [progress, setProgress] = useState<JobProgress | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => {
    getRealityScanDiagnostics().then(setDiag).catch((reason) => setError(reason.message));
    listRealityScanJobs(id).then(setJobs).catch((reason) => setError(reason.message));
    getJobStatus(id, "realityscan_prepare").then(setProgress).catch(() => undefined);
  };

  useEffect(load, [id]);

  useEffect(() => {
    if (!busy) return;
    let active = true;
    const poll = () => {
      getJobStatus(id, "realityscan_prepare").then((item) => {
        if (active) setProgress(item);
      }).catch(() => undefined);
      window.setTimeout(() => {
        if (active) poll();
      }, 1200);
    };
    poll();
    return () => {
      active = false;
    };
  }, [busy, id]);

  async function prepare() {
    setBusy(true);
    setError("");
    try {
      const job = await prepareRealityScanJob(id);
      setProgress(job.progress ?? null);
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Preparation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <div className="flex gap-4 text-sm text-slate-300">
          <Link href={`/projects/${id}/model-artifacts`}>Model Artifacts</Link>
          <Link href={`/projects/${id}/report`}>Report</Link>
        </div>
        <div className="glass-panel mt-5 rounded-lg p-7">
          <p className="text-sm text-brand">External photogrammetry</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">Prepare RealityScan Job</h1>
          <p className="mt-3 text-sm text-slate-400">
            Structura copies the validated image set into a RealityScan-ready job folder and writes a manual workflow draft.
            RealityScan remains the primary client-quality geometry path.
          </p>
          <div className="mt-5 rounded border border-white/10 p-4 text-sm">
            <p>Executable: {diag?.resolvedRealityScanExe ?? "Not found"}</p>
            <p className="mt-2">Source: {diag?.source ?? "Checking"} · Headless: {String(diag?.supportsHeadless ?? "unknown")} · Command file: {String(diag?.supportsCommandFile ?? "unknown")}</p>
            {diag?.errors.map((item) => <p key={item} className="mt-2 text-amber-100">{item}</p>)}
          </div>
          <button disabled={busy} onClick={prepare} className="mt-5 rounded bg-brand px-4 py-2 text-sm font-semibold text-ink disabled:opacity-50">
            {busy ? "Running..." : "Prepare RealityScan Job"}
          </button>
          {error && <p className="mt-3 text-red-200">{error}</p>}
          <div className="mt-5">
            <JobProgressCard progress={progress} title="RealityScan job preparation progress" />
          </div>
        </div>
        <section className="glass-panel mt-6 rounded-lg p-6">
          <h2 className="font-semibold text-white">Manual RealityScan workflow</h2>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-slate-300">
            <li>Open RealityScan and import the prepared job input folder.</li>
            <li>Align images, build model, and build texture.</li>
            <li>Export OBJ + MTL + textures as one ZIP.</li>
            <li>Import the ZIP through Model Artifacts.</li>
          </ol>
          {jobs.map((job) => (
            <div key={job.jobId} className="mt-4 rounded border border-white/10 p-4 text-sm text-slate-300">
              <p className="font-semibold">{job.status} · {job.imageCount ?? ""} images</p>
              <p className="mt-2 break-all">Input: {job.inputImageFolder}</p>
              <p className="break-all">Output: {job.outputFolder}</p>
              <p className="mt-2 break-all text-xs">Draft command file: {job.commandFilePath}</p>
            </div>
          ))}
        </section>
      </div>
    </AppShell>
  );
}
