import clsx from "clsx";
import type { ProjectStatus } from "@/lib/types";

export function statusLabel(status: ProjectStatus, hasPreview = false) {
  if (status === "Processing") return "Processing Capture";
  if (status === "Ready") return hasPreview ? "Preview Available" : "Ready for Reconstruction";
  if (status === "Reconstructing Sparse Model") return "Reconstructing Sparse Model";
  if (status === "Sparse Reconstruction Complete") return "Sparse Reconstruction Complete";
  if (status === "Sparse Reconstruction Failed") return "Sparse Reconstruction Failed";
  if (status === "Dense Reconstruction Running") return "Dense Reconstruction Running";
  if (status === "Dense Reconstruction Complete") return "Dense Reconstruction Complete";
  if (status === "Dense Reconstruction Failed") return "Dense Reconstruction Failed";
  return status;
}

export function StatusBadge({ status, hasPreview = false }: { status: ProjectStatus; hasPreview?: boolean }) {
  return (
    <span
      className={clsx(
        "inline-flex rounded-full border px-2.5 py-1 text-xs font-medium",
        status === "Ready" && "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
        status === "Processing" && "border-brand/30 bg-brand/10 text-cyan-100",
        status === "Reconstructing Sparse Model" && "border-brand/30 bg-brand/10 text-cyan-100",
        status === "Dense Reconstruction Running" && "border-brand/30 bg-brand/10 text-cyan-100",
        status === "Sparse Reconstruction Complete" && "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
        status === "Dense Reconstruction Complete" && "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
        status === "Sparse Reconstruction Failed" && "border-red-400/30 bg-red-400/10 text-red-100",
        status === "Dense Reconstruction Failed" && "border-red-400/30 bg-red-400/10 text-red-100",
        status === "Media Uploaded" && "border-violet-300/30 bg-violet-300/10 text-violet-100",
        status === "Draft" && "border-slate-400/20 bg-slate-400/10 text-slate-300"
      )}
    >
      {statusLabel(status, hasPreview)}
    </span>
  );
}
