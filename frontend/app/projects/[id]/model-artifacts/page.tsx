"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { createComparison, importModelArtifact, listComparisons, listModelArtifacts, modelArtifactDownloadUrl, setModelArtifactRole } from "@/lib/api";
import type { ArtifactComparison, ModelArtifact, ModelArtifactSummary } from "@/lib/types";
import { ArrowLeft, Download, FileUp, Layers3 } from "lucide-react";

const bytes = (value: number) => value < 1024 * 1024 ? `${Math.round(value / 1024)} KB` : `${(value / 1024 / 1024).toFixed(1)} MB`;
const splat = (artifact: ModelArtifact) => artifact.artifactType === "gaussian_splat" || artifact.stats.gaussianSplatDetected;

export default function ModelArtifactsPage() {
  const { id } = useParams<{ id: string }>();
  const [summary, setSummary] = useState<ModelArtifactSummary | null>(null);
  const [comparisons, setComparisons] = useState<ArtifactComparison[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [artifactType, setArtifactType] = useState("dense_point_cloud");
  const [sourceTool, setSourceTool] = useState("manual");
  const [role, setRole] = useState("current_state");
  const [notes, setNotes] = useState("");
  const [reference, setReference] = useState("");
  const [current, setCurrent] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const selectedReference = summary?.artifacts.find((item) => item.artifactId === reference);
  const selectedCurrent = summary?.artifacts.find((item) => item.artifactId === current);
  const selectedIncludesSplat = Boolean((selectedReference && splat(selectedReference)) || (selectedCurrent && splat(selectedCurrent)));

  const load = () => {
    listModelArtifacts(id).then((item) => {
      setSummary(item);
      setReference(item.latestReferenceModel?.artifactId ?? "");
      setCurrent(item.latestCurrentStateModel?.artifactId ?? "");
    }).catch((reason) => setError(reason.message));
    listComparisons(id).then(setComparisons).catch(() => setComparisons([]));
  };
  useEffect(load, [id]);

  async function upload() {
    if (!file) return setError("Choose a .ply or .obj file first.");
    setBusy(true); setError("");
    try { await importModelArtifact(id, file, { artifactType, sourceTool, notes, role }); setFile(null); setNotes(""); load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Import failed"); }
    finally { setBusy(false); }
  }
  async function compare() {
    if (!reference || !current) return setError("Select both a finished reference and current-state artifact.");
    setBusy(true); setError("");
    try { await createComparison(id, reference, current); load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Comparison could not be created"); }
    finally { setBusy(false); }
  }
  async function mark(artifactId: string, nextRole: string) {
    setBusy(true);
    try { await setModelArtifactRole(id, artifactId, nextRole); load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Role update failed"); }
    finally { setBusy(false); }
  }

  return <AppShell><div className="mx-auto max-w-5xl">
    <div className="flex flex-wrap items-center gap-3 text-sm text-slate-300">
      <Link href={`/projects/${id}/viewer`} className="inline-flex items-center gap-2 hover:text-white"><ArrowLeft size={16}/> Viewer</Link>
      <Link href={`/projects/${id}/visual-preview`} className="hover:text-white">Visual Preview</Link>
      <Link href={`/projects/${id}/report`} className="hover:text-white">Report</Link>
    </div>
    <div className="glass-panel mt-5 rounded-lg p-7">
      <div className="flex items-start justify-between gap-4"><div><p className="text-sm text-brand">Measurement / Progress pipeline</p><h1 className="mt-2 text-3xl font-semibold text-white">External Model Artifacts</h1><p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">This page is the measurement/progress pipeline foundation. Import dense point clouds or meshes from RealityCapture, Metashape, Pix4D, CloudCompare, or similar tools for real progress analysis.</p></div><Layers3 className="text-brand" size={30}/></div>
      <div className="mt-5 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">Gaussian Splat exports are visual-preview artifacts only and should not be used for measurement-grade progress comparison.</div>
      <div className="mt-6 grid gap-3 md:grid-cols-4"><input type="file" accept=".ply,.obj" onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="text-sm text-slate-300"/><select value={artifactType} onChange={(event) => setArtifactType(event.target.value)} className="rounded bg-slate-900 p-2 text-sm"><option value="dense_point_cloud">Dense point cloud</option><option value="mesh">Mesh</option><option value="textured_mesh">Textured mesh</option><option value="gaussian_splat">Gaussian Splat (preview only)</option></select><select value={sourceTool} onChange={(event) => setSourceTool(event.target.value)} className="rounded bg-slate-900 p-2 text-sm">{["manual", "realitycapture", "metashape", "pix4d", "cloudcompare"].map((item) => <option key={item}>{item}</option>)}</select><select value={role} onChange={(event) => setRole(event.target.value)} className="rounded bg-slate-900 p-2 text-sm"><option value="current_state">Current state</option><option value="finished_reference">Finished reference</option><option value="baseline">Baseline</option></select></div>
      {artifactType === "gaussian_splat" && <p className="mt-3 text-sm text-amber-100">Preview-only. Not measurement-grade. Do not use as finished/current progress comparison input.</p>}
      <input value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Notes (optional)" className="mt-3 w-full rounded border border-white/10 bg-slate-950 p-2 text-sm text-white"/>
      <button disabled={busy} onClick={upload} className="mt-3 inline-flex items-center gap-2 rounded bg-brand px-4 py-2 text-sm font-semibold text-ink disabled:opacity-50"><FileUp size={16}/> Import artifact</button>{error && <p className="mt-3 text-sm text-red-200">{error}</p>}
    </div>
    <section className="glass-panel mt-6 rounded-lg p-6"><h2 className="text-lg font-semibold text-white">Imported artifacts</h2>{!summary?.artifacts.length ? <p className="mt-3 text-sm text-slate-400">No external model artifacts yet.</p> : <div className="mt-4 space-y-3">{summary.artifacts.map((item) => <div key={item.artifactId} className="rounded border border-white/10 bg-white/[0.03] p-4"><div className="flex flex-wrap justify-between gap-3"><div><p className="font-medium text-white">{item.fileName}</p><p className="mt-1 text-xs text-slate-400">{item.artifactType.replaceAll("_", " ")} · {item.sourceTool} · {bytes(item.fileSize)} · {new Date(item.createdAt).toLocaleDateString()} {item.role ? `· ${item.role.replaceAll("_", " ")}` : ""}</p></div><a href={modelArtifactDownloadUrl(id, item.artifactId)} className="inline-flex items-center gap-2 text-sm text-brand"><Download size={15}/> Download</a></div><p className="mt-2 text-xs text-slate-400">Vertices: {item.stats.vertexCount ?? "unavailable"} · Faces: {item.stats.faceCount ?? "unavailable"}{item.stats.boundingBox ? ` · Bounds: (${item.stats.boundingBox.min.x.toFixed(2)}, ${item.stats.boundingBox.min.y.toFixed(2)}, ${item.stats.boundingBox.min.z.toFixed(2)}) → (${item.stats.boundingBox.max.x.toFixed(2)}, ${item.stats.boundingBox.max.y.toFixed(2)}, ${item.stats.boundingBox.max.z.toFixed(2)})` : ""}</p>{splat(item) && <p className="mt-2 text-sm text-amber-100">Preview-only. Not measurement-grade. Do not use as finished/current progress comparison input.</p>}{item.importWarning && <p className="mt-2 text-xs text-amber-100">{item.importWarning}</p>}<div className="mt-3 flex flex-wrap gap-3"><button disabled={busy} onClick={() => mark(item.artifactId, "current_state")} className="text-xs text-slate-300 hover:text-white">Mark current</button><button disabled={busy} onClick={() => mark(item.artifactId, "finished_reference")} className="text-xs text-slate-300 hover:text-white">Mark finished reference</button><button disabled={busy} onClick={() => mark(item.artifactId, "baseline")} className="text-xs text-slate-300 hover:text-white">Mark baseline</button></div></div>)}</div>}</section>
    <section className="glass-panel mt-6 rounded-lg p-6"><h2 className="text-lg font-semibold text-white">Progress comparison foundation</h2><p className="mt-2 text-sm text-slate-400">{summary?.message ?? "Loading artifact status..."} External alignment/distance analysis required; internal point cloud distance engine pending.</p><div className="mt-4 flex flex-wrap gap-3"><select value={reference} onChange={(event) => setReference(event.target.value)} className="rounded bg-slate-900 p-2 text-sm"><option value="">Finished reference</option>{summary?.artifacts.map((item) => <option key={item.artifactId} value={item.artifactId}>{item.fileName}</option>)}</select><select value={current} onChange={(event) => setCurrent(event.target.value)} className="rounded bg-slate-900 p-2 text-sm"><option value="">Current state</option>{summary?.artifacts.map((item) => <option key={item.artifactId} value={item.artifactId}>{item.fileName}</option>)}</select><button disabled={busy} onClick={compare} className="rounded border border-brand/50 px-4 py-2 text-sm text-brand disabled:opacity-50">Create comparison</button></div>{selectedIncludesSplat && <p className="mt-3 rounded border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">This comparison is a workflow placeholder only. Use dense point clouds or meshes for real progress measurement.</p>}{comparisons.map((comparison) => <div key={comparison.comparisonId} className="mt-3 rounded border border-white/10 p-3 text-sm text-slate-300"><p>Comparison foundation ready — {comparison.referenceArtifact.fileName} vs {comparison.currentArtifact.fileName}.</p>{comparison.warning && <p className="mt-2 text-amber-100">{comparison.warning}</p>}<p className="mt-2 text-slate-400">{comparison.recommendation}</p></div>)}</section>
  </div></AppShell>;
}
