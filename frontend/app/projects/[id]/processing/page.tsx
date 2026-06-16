"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { getProcessingStatus, getProject } from "@/lib/api";
import type { ProcessingStatus, Project } from "@/lib/types";
import { Check, Loader2 } from "lucide-react";

export default function ProcessingPage() {
  const params = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [status, setStatus] = useState<ProcessingStatus | null>(null);

  useEffect(() => {
    getProject(params.id).then(setProject).catch(() => setProject(null));
  }, [params.id]);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      const next = await getProcessingStatus(params.id);
      if (!active) return;
      setStatus(next);
      if (next.status !== "Ready") {
        window.setTimeout(poll, 1400);
      }
    };
    poll().catch(() => undefined);
    return () => {
      active = false;
    };
  }, [params.id]);

  const progress = status?.progress ?? 0;

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <p className="text-sm text-brand">Processing Digital Twin</p>
        <h1 className="mt-2 text-3xl font-semibold text-white">{project?.name ?? "Scan project"}</h1>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          Structura AI is simulating the reconstruction pipeline. Real FFmpeg, COLMAP, OpenMVS, and Blender CLI stages can be connected later.
        </p>

        <div className="glass-panel mt-8 rounded-lg p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm text-slate-400">Current step</p>
              <p className="mt-1 text-xl font-semibold text-white">{status?.currentStep ?? "Upload received"}</p>
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
              "Upload received",
              "Extracting frames",
              "Estimating camera positions",
              "Generating point cloud",
              "Building 3D model",
              "Exporting digital twin"
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

          {status?.status === "Ready" && (
            <Link href={`/projects/${params.id}/viewer`} className="mt-8 inline-flex rounded-md bg-brand px-5 py-3 font-semibold text-ink hover:bg-cyan-200">
              Open 3D Viewer
            </Link>
          )}
        </div>
      </div>
    </AppShell>
  );
}
