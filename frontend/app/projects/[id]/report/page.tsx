"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { getReport } from "@/lib/api";
import type { Report } from "@/lib/types";
import { ArrowLeft, CheckCircle2 } from "lucide-react";

export default function ReportPage() {
  const params = useParams<{ id: string }>();
  const [report, setReport] = useState<Report | null>(null);

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
              <p className="mt-2 text-base font-semibold text-white">{report?.detectedOutput ?? "Interactive 3D model"}</p>
            </div>
          </div>

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
