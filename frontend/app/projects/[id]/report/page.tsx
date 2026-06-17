"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { getReport } from "@/lib/api";
import type { Report } from "@/lib/types";
import { AlertTriangle, ArrowLeft, CheckCircle2 } from "lucide-react";

export default function ReportPage() {
  const params = useParams<{ id: string }>();
  const [report, setReport] = useState<Report | null>(null);
  const denseLogEntries = Object.entries(report?.reconstructionMetadata?.denseLogPreviewSummary ?? {}).filter(([, value]) => value.trim().length > 0);

  useEffect(() => {
    getReport(params.id).then(setReport).catch(() => setReport(null));
  }, [params.id]);

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <Link href={`/projects/${params.id}/viewer`} className="inline-flex items-center gap-2 text-sm text-slate-300 hover:text-white">
          <ArrowLeft size={16} /> Back to viewer
        </Link>

        <div className="glass-panel mt-5 rounded-lg p-8">
          <p className="text-sm text-brand">Structura AI Scan Summary</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">{report?.projectName ?? "Scan report"}</h1>
          <p className="mt-3 text-sm leading-6 text-slate-400">
            Mentor-ready prototype report generated from the local project metadata, uploaded media, processing status, and inspection annotations.
          </p>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Uploaded media</p>
              <p className="mt-2 text-2xl font-semibold text-white">{report?.uploadedMediaCount ?? 0}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Processing status</p>
              <p className="mt-2 text-2xl font-semibold text-white">{report?.processingStatus ?? "Draft"}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Detected output</p>
              <p className="mt-2 text-base font-semibold text-white">{report?.detectedOutput ?? "Prototype digital twin preview"}</p>
            </div>
          </div>

          <section className="mt-8">
            <h2 className="font-semibold text-white">Capture metadata</h2>
            <div className="mt-3 grid gap-4 md:grid-cols-4">
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Extracted frames</p>
                <p className="mt-2 text-2xl font-semibold text-white">{report?.captureMetadata?.extractedFrameCount ?? 0}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Images</p>
                <p className="mt-2 text-2xl font-semibold text-white">{report?.captureMetadata?.imageCount ?? 0}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Videos</p>
                <p className="mt-2 text-2xl font-semibold text-white">{report?.captureMetadata?.videoCount ?? 0}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Workspace</p>
                <p className="mt-2 text-sm font-semibold text-white">{report?.captureMetadata?.workspacePrepared ? "Prepared" : "Pending"}</p>
              </div>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-4">
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Selected FPS</p>
                <p className="mt-2 text-sm font-semibold text-white">{report?.captureMetadata?.selectedFpsMode ?? "Balanced"} ({report?.captureMetadata?.extractionFps ?? 2} FPS)</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Average sharpness</p>
                <p className="mt-2 text-sm font-semibold text-white">{report?.captureMetadata?.sharpnessAvailable ? report.captureMetadata.averageSharpness?.toFixed(2) : "Unavailable"}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Blurry frames</p>
                <p className="mt-2 text-sm font-semibold text-white">{report?.captureMetadata?.blurryFrameCount ?? 0}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Readiness</p>
                <p className="mt-2 text-sm font-semibold text-white">{report?.captureMetadata?.readinessLabel ?? "Poor Capture"}</p>
              </div>
            </div>
            {(report?.warnings ?? []).length > 0 && (
              <div className="mt-4 space-y-3">
                {(report?.warnings ?? []).map((warning) => (
                  <div key={warning} className="flex items-center gap-3 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">
                    <AlertTriangle size={17} />
                    {warning}
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="mt-8">
            <h2 className="font-semibold text-white">Reconstruction output</h2>
            <div className="mt-3 grid gap-4 md:grid-cols-5">
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Sparse status</p>
                <p className="mt-2 text-sm font-semibold text-white">{report?.reconstructionMetadata?.sparseStatus ?? report?.reconstructionMetadata?.status ?? "Not Started"}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Dense status</p>
                <p className="mt-2 text-sm font-semibold text-white">{report?.reconstructionMetadata?.denseStatus ?? "Dense Reconstruction Not Started"}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Sparse points</p>
                <p className="mt-2 text-2xl font-semibold text-white">{report?.reconstructionMetadata?.sparsePointCount ?? report?.reconstructionMetadata?.pointCount ?? 0}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Dense points</p>
                <p className="mt-2 text-2xl font-semibold text-white">{report?.reconstructionMetadata?.densePointCount ?? 0}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Next action</p>
                <p className="mt-2 text-sm font-semibold text-white">{report?.reconstructionMetadata?.recommendedNextAction ?? "Run sparse reconstruction"}</p>
              </div>
            </div>
            <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Matching mode used</p>
              <p className="mt-2 text-sm font-semibold text-white">{report?.reconstructionMetadata?.matchingModeUsed ?? "Not Started"}</p>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">COLMAP detected</p>
                <p className="mt-2 text-sm font-semibold text-white">{report?.reconstructionMetadata?.colmapAvailable ? "Yes" : "No"}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">CUDA / dense support hint</p>
                <p className="mt-2 text-sm font-semibold text-white">{report?.reconstructionMetadata?.colmapCudaHint ?? "Unknown"}</p>
              </div>
            </div>
            {report?.reconstructionMetadata?.denseStatus === "Dense Reconstruction Failed" && (
              <div className="mt-4 rounded-md border border-red-400/30 bg-red-400/10 p-4 text-sm text-red-100">
                <p className="font-semibold">Dense reconstruction failure details</p>
                <p className="mt-1">{report.reconstructionMetadata.denseErrorMessage ?? "Dense reconstruction failed."}</p>
                {(report.reconstructionMetadata.denseLikelyCauses ?? []).length > 0 && (
                  <p className="mt-2 text-xs text-red-100/80">Likely causes: {(report.reconstructionMetadata.denseLikelyCauses ?? []).join(", ")}.</p>
                )}
                {denseLogEntries.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {denseLogEntries.map(([name, preview]) => (
                      <div key={name} className="rounded-md border border-red-200/10 bg-slate-950/70 p-3">
                        <p className="text-xs font-semibold uppercase text-red-100/80">{name}</p>
                        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs leading-5 text-red-50/80">{preview}</pre>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="mt-8">
            <h2 className="font-semibold text-white">Annotations</h2>
            <div className="mt-3 space-y-3">
              {(report?.annotations ?? []).map((annotation) => (
                <div key={annotation.id} className="rounded-md border border-white/10 bg-slate-950/70 p-3 text-sm text-slate-200">
                  {annotation.text}
                </div>
              ))}
            </div>
          </section>

          <section className="mt-8">
            <h2 className="font-semibold text-white">Prototype limitations</h2>
            <div className="mt-3 space-y-3">
              {(report?.limitations ?? [
                "Measurements are approximate in this prototype",
                "Full building-scale reconstruction will be added in later phases"
              ]).map((limitation) => (
                <div key={limitation} className="flex items-center gap-3 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">
                  <CheckCircle2 size={17} />
                  {limitation}
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </AppShell>
  );
}
