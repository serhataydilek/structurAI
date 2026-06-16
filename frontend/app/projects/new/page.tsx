"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { createProject } from "@/lib/api";

const siteTypes = ["Condo Interior", "Apartment", "Office", "Construction Site", "Other"];

export default function NewProjectPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [siteType, setSiteType] = useState(siteTypes[0]);
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const project = await createProject({ name, siteType, description });
      router.push(`/projects/${project.id}/upload`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create project");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl">
        <p className="text-sm text-brand">New Scan Project</p>
        <h1 className="mt-2 text-3xl font-semibold text-white">Set up a controlled capture</h1>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          The MVP starts with condo and interior captures for reliable testing, while the workflow is designed for larger building scans.
        </p>

        <form onSubmit={onSubmit} className="glass-panel mt-8 rounded-lg p-6">
          <label className="block text-sm font-medium text-slate-200">
            Project name
            <input required value={name} onChange={(event) => setName(event.target.value)} className="mt-2 w-full rounded-md border border-white/10 bg-slate-950 px-3 py-3 text-white outline-none focus:border-brand" placeholder="Condo inspection demo" />
          </label>

          <label className="mt-5 block text-sm font-medium text-slate-200">
            Site/building type
            <select value={siteType} onChange={(event) => setSiteType(event.target.value)} className="mt-2 w-full rounded-md border border-white/10 bg-slate-950 px-3 py-3 text-white outline-none focus:border-brand">
              {siteTypes.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>

          <label className="mt-5 block text-sm font-medium text-slate-200">
            Description
            <textarea value={description} onChange={(event) => setDescription(event.target.value)} className="mt-2 min-h-32 w-full rounded-md border border-white/10 bg-slate-950 px-3 py-3 text-white outline-none focus:border-brand" placeholder="Capture goal, site context, or inspection notes." />
          </label>

          {error && <p className="mt-4 rounded-md border border-red-400/30 bg-red-400/10 px-3 py-2 text-sm text-red-100">{error}</p>}

          <button disabled={saving} className="mt-6 rounded-md bg-brand px-5 py-3 font-semibold text-ink hover:bg-cyan-200 disabled:opacity-60">
            {saving ? "Creating..." : "Create and Continue"}
          </button>
        </form>
      </div>
    </AppShell>
  );
}
