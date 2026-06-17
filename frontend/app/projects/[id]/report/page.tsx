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
  const bestAttempt = report?.reconstructionMetadata?.bestAttempt;
  const latestAttempt = report?.reconstructionMetadata?.latestAttempt;
  const latestDiffersFromBest = Boolean(bestAttempt && latestAttempt && bestAttempt.attemptId !== latestAttempt.attemptId);
  const sparseQualityPoor = report?.reconstructionMetadata?.sparseQualityLabel === "Poor Sparse Reconstruction";
  const selectedFrameCount = report?.reconstructionMetadata?.selectedFrameCount ?? report?.reconstructionMetadata?.extractedFrameCount ?? 0;
  const registeredImageCount = report?.reconstructionMetadata?.registeredImageCount ?? 0;
  const selectedRegistrationPercent = Math.round((report?.reconstructionMetadata?.selectedRegistrationRatio ?? report?.reconstructionMetadata?.registrationRatio ?? 0) * 100);
  const photoSetRecommendations = [
    "Take 40-80 sharp photos.",
    "Keep 60-70% overlap between photos.",
    "Keep the same objects visible across multiple photos.",
    "Capture corners, doors, windows, furniture, and textured objects.",
    "Avoid blank walls, mirrors, glass, and shiny surfaces.",
    "Use Photo Exhaustive matching for photo sets."
  ];

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
              <p className="mt-2 text-base font-semibold text-white">{report?.detectedOutput ?? "No reconstruction output yet"}</p>
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
            <div className="mt-4 grid gap-4 md:grid-cols-4">
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Extracted frames</p>
                <p className="mt-2 text-2xl font-semibold text-white">{report?.reconstructionMetadata?.extractedFrameCount ?? report?.reconstructionMetadata?.inputFrameCount ?? report?.captureMetadata?.extractedFrameCount ?? 0}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Registered images</p>
                <p className="mt-2 text-2xl font-semibold text-white">{report?.reconstructionMetadata?.registeredImageCount ?? 0}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Registration ratio</p>
                <p className="mt-2 text-2xl font-semibold text-white">{report?.reconstructionMetadata?.registrationRatioLabel ?? "0%"}</p>
                <p className="mt-1 text-xs text-slate-500">{report?.reconstructionMetadata?.sourceFrameCount ?? report?.reconstructionMetadata?.extractedFrameCount ?? 0} source frames</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Sparse quality</p>
                <p className="mt-2 text-sm font-semibold text-white">{report?.reconstructionMetadata?.sparseQualityLabel ?? "Not Started"}</p>
              </div>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-3">
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Frame selection</p>
                <p className="mt-2 text-sm font-semibold text-white">{report?.reconstructionMetadata?.frameSelectionMode ?? "All frames"}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Selected frames</p>
                <p className="mt-2 text-sm font-semibold text-white">{report?.reconstructionMetadata?.selectedFrameCount ?? report?.reconstructionMetadata?.extractedFrameCount ?? 0}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs text-slate-500">Source frames</p>
                <p className="mt-2 text-sm font-semibold text-white">{report?.reconstructionMetadata?.sourceFrameCount ?? report?.reconstructionMetadata?.extractedFrameCount ?? 0}</p>
              </div>
            </div>
            <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-slate-500">Matching mode used</p>
              <p className="mt-2 text-sm font-semibold text-white">{report?.reconstructionMetadata?.matchingModeUsed ?? "Not Started"}</p>
            </div>
            {sparseQualityPoor && (
              <div className="mt-4 rounded-lg border border-red-400/30 bg-red-400/10 p-5 text-red-50">
                <p className="text-base font-semibold">
                  COLMAP could only register {registeredImageCount} out of {selectedFrameCount} selected frames. The reconstruction is too weak to produce a readable scene.
                </p>
                <div className="mt-4 grid gap-3 md:grid-cols-4">
                  <div>
                    <p className="text-xs text-red-100/70">Selected frames</p>
                    <p className="text-lg font-semibold">{selectedFrameCount}</p>
                  </div>
                  <div>
                    <p className="text-xs text-red-100/70">Registered images</p>
                    <p className="text-lg font-semibold">{registeredImageCount}</p>
                  </div>
                  <div>
                    <p className="text-xs text-red-100/70">Selected registration ratio</p>
                    <p className="text-lg font-semibold">{selectedRegistrationPercent}%</p>
                  </div>
                  <div>
                    <p className="text-xs text-red-100/70">Sparse points</p>
                    <p className="text-lg font-semibold">{report?.reconstructionMetadata?.sparsePointCount ?? 0}</p>
                  </div>
                </div>
                <p className="mt-3 text-sm text-red-100/85">Likely reason: Most frames could not be reliably matched.</p>
                <p className="mt-3 text-sm font-semibold text-red-50">Next action: Improve capture and rerun sparse reconstruction.</p>
              </div>
            )}
            {sparseQualityPoor && (
              <div className="mt-4 rounded-lg border border-emerald-300/20 bg-emerald-300/10 p-5">
                <p className="text-base font-semibold text-emerald-100">Video capture is failing. Try a sharp photo set instead.</p>
                <ul className="mt-3 grid gap-2 text-sm text-emerald-50/90 md:grid-cols-2">
                  {photoSetRecommendations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {report?.detectedOutput === "Sparse scene preview" && (
              <div className="mt-4 rounded-lg border border-brand/25 bg-brand/10 p-4 text-sm text-cyan-50">
                The preview combines sparse COLMAP points with estimated room bounds. It is a readability layer before dense reconstruction or mesh generation, not a final digital twin.
              </div>
            )}
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
            {(report?.reconstructionMetadata?.denseReadiness?.reasons ?? []).length > 0 && (
              <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs font-semibold text-slate-300">Dense readiness notes</p>
                <ul className="mt-2 space-y-1 text-sm text-slate-400">
                  {(report?.reconstructionMetadata?.denseReadiness?.reasons ?? []).map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </div>
            )}
            {bestAttempt && (
              <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs font-semibold text-slate-300">Best sparse attempt</p>
                <p className="mt-2 text-sm font-semibold text-white">{bestAttempt.label}</p>
                {latestDiffersFromBest && latestAttempt && (
                  <p className="mt-2 text-sm text-amber-100">
                    Latest run is worse than the best stored attempt: {latestAttempt.label}. The report uses the best attempt by default.
                  </p>
                )}
              </div>
            )}
            {(report?.reconstructionMetadata?.reconstructionAttempts ?? []).length > 0 && (
              <div className="mt-4 overflow-hidden rounded-md border border-white/10">
                <table className="w-full text-left text-sm">
                  <thead className="bg-white/[0.04] text-xs text-slate-400">
                    <tr>
                      <th className="px-3 py-2">Mode</th>
                      <th className="px-3 py-2">Matching</th>
                      <th className="px-3 py-2">Selected</th>
                      <th className="px-3 py-2">Registered</th>
                      <th className="px-3 py-2">Ratio</th>
                      <th className="px-3 py-2">Points</th>
                      <th className="px-3 py-2">Best</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10">
                    {(report?.reconstructionMetadata?.reconstructionAttempts ?? []).map((attempt) => (
                      <tr key={attempt.attemptId} className="text-slate-200">
                        <td className="px-3 py-2">{attempt.frameSelectionMode ?? "All frames"}</td>
                        <td className="px-3 py-2">{attempt.matchingMode}</td>
                        <td className="px-3 py-2">{attempt.selectedFrameCount ?? attempt.extractedFrameCount}</td>
                        <td className="px-3 py-2">{attempt.registeredImageCount}</td>
                        <td className="px-3 py-2">{attempt.registrationRatioLabel ?? `${Math.round(attempt.registrationRatio * 100)}%`}</td>
                        <td className="px-3 py-2">{attempt.sparsePointCount}</td>
                        <td className="px-3 py-2">{attempt.isBestAttempt ? "Yes" : "No"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {(report?.reconstructionMetadata?.lowRegistrationRecommendations ?? []).length > 0 && (
              <div className="mt-4 rounded-md border border-amber-300/20 bg-amber-300/10 p-4">
                <p className="text-sm font-semibold text-amber-100">Capture recommendations</p>
                <ul className="mt-2 space-y-1 text-sm text-amber-100/80">
                  {(report?.reconstructionMetadata?.lowRegistrationRecommendations ?? []).map((recommendation) => (
                    <li key={recommendation}>{recommendation}</li>
                  ))}
                </ul>
              </div>
            )}
            {report?.reconstructionMetadata?.denseStatus === "Dense Reconstruction Failed" && (
              <div className="mt-4 rounded-md border border-red-400/30 bg-red-400/10 p-4 text-sm text-red-100">
                <p className="font-semibold">Dense reconstruction failure details</p>
                <p className="mt-1">{report.reconstructionMetadata.denseErrorMessage ?? "Dense reconstruction failed."}</p>
                {(report.reconstructionMetadata.denseLikelyCauses ?? []).length > 0 && (
                  <p className="mt-2 text-xs text-red-100/80">Likely causes: {(report.reconstructionMetadata.denseLikelyCauses ?? []).join(", ")}.</p>
                )}
                {denseLogEntries.length > 0 && (
                  <details className="mt-3 rounded-md border border-red-200/10 bg-slate-950/70 p-3">
                    <summary className="cursor-pointer text-xs font-semibold text-red-100/80">Technical dense logs</summary>
                    <div className="mt-3 space-y-2">
                      {denseLogEntries.map(([name, preview]) => (
                        <div key={name} className="rounded-md border border-red-200/10 bg-slate-950/70 p-3">
                          <p className="text-xs font-semibold uppercase text-red-100/80">{name}</p>
                          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs leading-5 text-red-50/80">{preview}</pre>
                        </div>
                      ))}
                    </div>
                  </details>
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
