"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { StatusBadge, statusLabel } from "@/components/StatusBadge";
import { deleteProject, listProjects, resetDevData } from "@/lib/api";
import type { Project } from "@/lib/types";
import { ArrowRight, Boxes, Plus, Search, Trash2 } from "lucide-react";

type Filter = "All" | "Draft" | "Media Uploaded" | "Processing" | "Ready" | "Ready for Reconstruction" | "Preview Available";

const filters: Filter[] = ["All", "Draft", "Media Uploaded", "Processing", "Ready", "Ready for Reconstruction", "Preview Available"];

function projectRoute(project: Project) {
  if (
    project.status === "Ready" ||
    project.status === "Processing" ||
    project.status === "Reconstructing Sparse Model" ||
    project.status === "Sparse Reconstruction Complete" ||
    project.status === "Sparse Reconstruction Failed"
  ) return `/projects/${project.id}/processing`;
  return `/projects/${project.id}/upload`;
}

function matchesFilter(project: Project, filter: Filter) {
  if (filter === "All") return true;
  if (filter === "Processing") return project.status === "Processing";
  if (filter === "Ready") return project.status === "Ready";
  if (filter === "Ready for Reconstruction") return project.status === "Ready";
  if (filter === "Preview Available") return false;
  return project.status === filter;
}

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("All");

  async function refreshProjects() {
    setLoading(true);
    listProjects()
      .then(setProjects)
      .catch(() => setProjects([]))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    refreshProjects();
  }, []);

  const counts = useMemo(
    () => ({
      total: projects.length,
      ready: projects.filter((project) => project.status === "Ready").length,
      processing: projects.filter((project) => project.status === "Processing").length
    }),
    [projects]
  );

  const visibleProjects = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return projects.filter((project) => {
      const queryMatch = !normalized || project.name.toLowerCase().includes(normalized);
      return queryMatch && matchesFilter(project, filter);
    });
  }, [projects, query, filter]);

  async function onDelete(project: Project) {
    const confirmed = window.confirm(`Delete "${project.name}" and remove its local uploads, frames, annotations, and capture metadata?`);
    if (!confirmed) return;
    await deleteProject(project.id);
    setProjects((current) => current.filter((item) => item.id !== project.id));
  }

  async function onReset() {
    const confirmed = window.confirm("Reset all local demo data? This deletes every project plus uploaded and processed files on this machine.");
    if (!confirmed) return;
    await resetDevData();
    setProjects([]);
  }

  return (
    <AppShell>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-brand">Scan Projects</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">Capture processing dashboard</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-400">
            Structura validates captures, manages external photogrammetry artifacts, and reports measurement/progress readiness. Client-quality geometry comes from RealityScan, Metashape, Pix4D, or similar tools.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button onClick={onReset} className="inline-flex items-center gap-2 rounded-md border border-red-400/30 px-4 py-2.5 text-sm font-semibold text-red-100 hover:bg-red-400/10">
            <Trash2 size={16} /> Reset local demo data
          </button>
          <Link href="/projects/new" className="inline-flex items-center gap-2 rounded-md bg-brand px-4 py-2.5 font-semibold text-ink hover:bg-cyan-200">
            <Plus size={18} /> New Scan Project
          </Link>
        </div>
      </div>

      <div className="mb-5 grid gap-4 md:grid-cols-3">
        <div className="glass-panel rounded-lg p-4">
          <p className="text-xs text-slate-500">Total projects</p>
          <p className="mt-2 text-2xl font-semibold text-white">{counts.total}</p>
        </div>
        <div className="glass-panel rounded-lg p-4">
          <p className="text-xs text-slate-500">Ready projects</p>
          <p className="mt-2 text-2xl font-semibold text-white">{counts.ready}</p>
        </div>
        <div className="glass-panel rounded-lg p-4">
          <p className="text-xs text-slate-500">Processing projects</p>
          <p className="mt-2 text-2xl font-semibold text-white">{counts.processing}</p>
        </div>
      </div>

      <div className="mb-6 flex flex-col gap-3 rounded-lg border border-white/10 bg-white/[0.03] p-3 md:flex-row md:items-center md:justify-between">
        <label className="flex min-w-0 flex-1 items-center gap-2 rounded-md border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-300">
          <Search size={16} className="text-slate-500" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} className="min-w-0 flex-1 bg-transparent text-white outline-none" placeholder="Search projects" />
        </label>
        <div className="flex flex-wrap gap-2">
          {filters.map((item) => (
            <button
              key={item}
              onClick={() => setFilter(item)}
              className={`rounded-md border px-3 py-2 text-xs font-medium ${
                filter === item ? "border-brand bg-brand text-ink" : "border-white/10 text-slate-300 hover:bg-white/10"
              }`}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="glass-panel rounded-lg p-8 text-slate-300">Loading scan projects...</div>
      ) : projects.length === 0 ? (
        <div className="glass-panel rounded-lg p-10 text-center">
          <Boxes className="mx-auto text-brand" size={36} />
          <h2 className="mt-4 text-xl font-semibold text-white">No scan projects yet. Create your first building capture project.</h2>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-slate-400">
            Start with a controlled condo or interior capture, then review extracted frames before future reconstruction.
          </p>
          <Link href="/projects/new" className="mt-6 inline-flex items-center gap-2 rounded-md bg-brand px-4 py-2.5 font-semibold text-ink hover:bg-cyan-200">
            Start Scan Demo <ArrowRight size={17} />
          </Link>
        </div>
      ) : visibleProjects.length === 0 ? (
        <div className="glass-panel rounded-lg p-8 text-center text-slate-300">No projects match the current search and filter.</div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visibleProjects.map((project) => (
            <div key={project.id} className="glass-panel rounded-lg p-5 transition hover:border-brand/40">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-semibold text-white">{project.name}</h2>
                  <p className="mt-1 text-sm text-slate-400">{project.scan_type}</p>
                </div>
                <StatusBadge status={project.status} />
              </div>
              <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                  <p className="text-xs text-slate-500">Media</p>
                  <p className="mt-1 text-slate-100">{project.mediaCount ?? 0}</p>
                </div>
                <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                  <p className="text-xs text-slate-500">Frames</p>
                  <p className="mt-1 text-slate-100">{project.extractedFrameCount ?? 0}</p>
                </div>
              </div>
              <p className="mt-4 text-sm text-slate-400">Created {new Date(project.created_at).toLocaleDateString()}</p>
              <p className="mt-2 text-xs text-slate-500">Status: {statusLabel(project.status)}</p>
              <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4 text-sm">
                <div className="flex gap-3">
                  <Link href={projectRoute(project)} className="inline-flex items-center gap-2 text-cyan-100 hover:text-brand">
                    Open project <ArrowRight size={16} />
                  </Link>
                  <Link href={`/projects/${project.id}/model-artifacts`} className="text-slate-300 hover:text-brand">Model Artifacts</Link>
                </div>
                <button onClick={() => onDelete(project)} className="inline-flex items-center gap-2 rounded-md border border-red-400/30 px-3 py-2 text-xs font-semibold text-red-100 hover:bg-red-400/10">
                  <Trash2 size={14} /> Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </AppShell>
  );
}
