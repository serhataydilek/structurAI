"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/StatusBadge";
import { ViewerScene } from "@/components/ViewerScene";
import { addAnnotation, getModel, getProject, listAnnotations } from "@/lib/api";
import type { Annotation, Project } from "@/lib/types";
import { FileText, Plus } from "lucide-react";

export default function ViewerPage() {
  const params = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [note, setNote] = useState("");
  const [modelUrl, setModelUrl] = useState<string | undefined>();

  useEffect(() => {
    getProject(params.id).then(setProject).catch(() => setProject(null));
    listAnnotations(params.id).then(setAnnotations).catch(() => setAnnotations([]));
    getModel(params.id)
      .then(async (model) => {
        const response = await fetch(model.modelUrl, { method: "HEAD" });
        setModelUrl(response.ok ? model.modelUrl : undefined);
      })
      .catch(() => setModelUrl(undefined));
  }, [params.id]);

  async function submitNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!note.trim()) return;
    const created = await addAnnotation(params.id, note);
    setAnnotations((current) => [...current, created]);
    setNote("");
  }

  return (
    <AppShell>
      <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
        <section>
          <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm text-brand">Interactive Digital Twin</p>
              <h1 className="mt-2 text-3xl font-semibold text-white">{project?.name ?? "Scan project"}</h1>
              <p className="mt-2 text-sm text-slate-400">
                Prototype digital twin preview
              </p>
            </div>
            <Link href={`/projects/${params.id}/report`} className="inline-flex items-center gap-2 rounded-md bg-brand px-4 py-2.5 font-semibold text-ink hover:bg-cyan-200">
              <FileText size={17} /> Export Report
            </Link>
          </div>
          <ViewerScene modelUrl={modelUrl} />
        </section>

        <aside className="glass-panel rounded-lg p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold text-white">Project info</h2>
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
