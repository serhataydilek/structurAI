"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/StatusBadge";
import { listProjects } from "@/lib/api";
import type { Project } from "@/lib/types";
import { ArrowRight, Boxes, Plus } from "lucide-react";

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch(() => setProjects([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppShell>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-brand">Scan Projects</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">Digital twin dashboard</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-400">
            Manage controlled interior captures today while keeping the workflow aligned with building-scale digital twins.
          </p>
        </div>
        <Link href="/projects/new" className="inline-flex items-center gap-2 rounded-md bg-brand px-4 py-2.5 font-semibold text-ink hover:bg-cyan-200">
          <Plus size={18} /> New Scan Project
        </Link>
      </div>

      {loading ? (
        <div className="glass-panel rounded-lg p-8 text-slate-300">Loading scan projects...</div>
      ) : projects.length === 0 ? (
        <div className="glass-panel rounded-lg p-10 text-center">
          <Boxes className="mx-auto text-brand" size={36} />
          <h2 className="mt-4 text-xl font-semibold text-white">No scan projects yet</h2>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-slate-400">
            Start with a controlled condo or interior capture, upload sample media, and generate a simulated interactive digital twin.
          </p>
          <Link href="/projects/new" className="mt-6 inline-flex items-center gap-2 rounded-md bg-brand px-4 py-2.5 font-semibold text-ink hover:bg-cyan-200">
            Start Scan Demo <ArrowRight size={17} />
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {projects.map((project) => (
            <Link key={project.id} href={`/projects/${project.id}/${project.status === "Ready" ? "viewer" : project.status === "Processing" ? "processing" : "upload"}`} className="glass-panel rounded-lg p-5 transition hover:border-brand/40">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-semibold text-white">{project.name}</h2>
                  <p className="mt-1 text-sm text-slate-400">{project.scan_type}</p>
                </div>
                <StatusBadge status={project.status} />
              </div>
              <p className="mt-5 text-sm text-slate-400">Created {new Date(project.created_at).toLocaleDateString()}</p>
              <div className="mt-5 flex items-center justify-between border-t border-white/10 pt-4 text-sm text-cyan-100">
                Open project <ArrowRight size={16} />
              </div>
            </Link>
          ))}
        </div>
      )}
    </AppShell>
  );
}
