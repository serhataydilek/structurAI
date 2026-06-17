"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { getProject, uploadMedia } from "@/lib/api";
import type { ExtractionFpsMode, Project } from "@/lib/types";
import { CheckCircle2, UploadCloud } from "lucide-react";

const guidance = [
  "Move slowly",
  "Keep 60-80% overlap",
  "Capture corners",
  "Avoid mirrors and glass",
  "Use good lighting",
  "Capture from multiple angles"
];

const fpsOptions: { mode: ExtractionFpsMode; label: string; description: string }[] = [
  { mode: "Fast", label: "Fast 1 FPS", description: "Faster processing for quick checks." },
  { mode: "Balanced", label: "Balanced 2 FPS", description: "Recommended default for room captures." },
  { mode: "Detailed", label: "Detailed 3 FPS", description: "More frames for COLMAP, longer processing." }
];

export default function UploadPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [extractionFpsMode, setExtractionFpsMode] = useState<ExtractionFpsMode>("Balanced");
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [success, setSuccess] = useState("");

  useEffect(() => {
    getProject(params.id).then(setProject).catch(() => setProject(null));
  }, [params.id]);

  const videoCount = useMemo(() => files.filter((file) => file.type.startsWith("video/")).length, [files]);

  function onFiles(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? []);
    setError("");
    if (selected.some((file) => !file.type.startsWith("image/") && !file.type.startsWith("video/"))) {
      setError("Upload images or one video file only.");
      return;
    }
    if (selected.filter((file) => file.type.startsWith("video/")).length > 1) {
      setError("Only one video can be uploaded per project.");
      return;
    }
    setFiles(selected);
  }

  async function submitUpload() {
    if (files.length === 0) {
      setError("Choose at least one image or one video before uploading.");
      return;
    }
    setUploading(true);
    setError("");
    setSuccess("");
    try {
      await uploadMedia(params.id, files);
      setSuccess("Upload complete. Starting frame extraction...");
      router.push(`/projects/${params.id}/processing?autostart=1&fps=${extractionFpsMode}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <AppShell>
      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <section>
          <p className="text-sm text-brand">Upload Capture Media</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">{project?.name ?? "Scan project"}</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
            Add overlapping photos or a single walkthrough video. This build stores media locally and prepares real frames for a later reconstruction stage.
          </p>

          <div className="glass-panel mt-8 rounded-lg p-6">
            <label className="flex min-h-64 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-brand/35 bg-brand/5 px-6 py-10 text-center hover:bg-brand/10">
              <UploadCloud className="text-brand" size={38} />
              <span className="mt-4 text-lg font-semibold text-white">Select images and optional video</span>
              <span className="mt-2 text-sm text-slate-400">Multiple images are supported. Only one video is allowed.</span>
              <input className="hidden" type="file" multiple accept="image/*,video/*" onChange={onFiles} />
            </label>

            {files.length > 0 && (
              <div className="mt-5 rounded-lg border border-white/10 bg-slate-950/70 p-4">
                <div className="mb-3 flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-200">{files.length} file(s) selected</span>
                  <span className="text-slate-400">{videoCount} video</span>
                </div>
                <ul className="max-h-44 space-y-2 overflow-auto text-sm text-slate-400">
                  {files.map((file) => (
                    <li key={`${file.name}-${file.size}`} className="flex justify-between gap-4 rounded-md bg-white/[0.03] px-3 py-2">
                      <span className="truncate">{file.name}</span>
                      <span>{Math.round(file.size / 1024)} KB</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {success && <p className="mt-4 rounded-md border border-emerald-300/30 bg-emerald-300/10 px-3 py-2 text-sm text-emerald-100">{success}</p>}
            {error && <p className="mt-4 rounded-md border border-red-400/30 bg-red-400/10 px-3 py-2 text-sm text-red-100">{error}</p>}

            <div className="mt-5 rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-sm font-semibold text-white">Video extraction FPS</p>
              <p className="mt-1 text-xs text-slate-400">Higher FPS gives COLMAP more frames but takes longer.</p>
              <div className="mt-3 grid gap-2 md:grid-cols-3">
                {fpsOptions.map((option) => (
                  <button
                    key={option.mode}
                    type="button"
                    onClick={() => setExtractionFpsMode(option.mode)}
                    className={`rounded-md border px-3 py-3 text-left text-sm transition ${
                      extractionFpsMode === option.mode
                        ? "border-brand bg-brand/10 text-white"
                        : "border-white/10 bg-slate-950/50 text-slate-300 hover:bg-white/10"
                    }`}
                  >
                    <span className="font-semibold">{option.label}</span>
                    {option.mode === "Balanced" && <span className="ml-2 text-xs text-brand">Recommended</span>}
                    <span className="mt-1 block text-xs text-slate-500">{option.description}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              <button disabled={uploading} onClick={submitUpload} className="rounded-md bg-brand px-5 py-3 font-semibold text-ink hover:bg-cyan-200 disabled:opacity-60">
                {uploading ? "Uploading..." : "Upload and Process"}
              </button>
              <Link href="/dashboard" className="rounded-md border border-white/10 px-5 py-3 text-slate-200 hover:bg-white/10">
                Back to Dashboard
              </Link>
            </div>
          </div>
        </section>

        <aside className="glass-panel rounded-lg p-5">
          <h2 className="font-semibold text-white">Capture guidance</h2>
          <div className="mt-4 space-y-3">
            {guidance.map((item) => (
              <div key={item} className="flex items-center gap-3 rounded-md border border-white/10 bg-white/[0.03] px-3 py-3 text-sm text-slate-200">
                <CheckCircle2 size={17} className="text-brand" />
                {item}
              </div>
            ))}
          </div>
        </aside>
      </div>
    </AppShell>
  );
}
