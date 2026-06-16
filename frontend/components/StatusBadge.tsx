import clsx from "clsx";
import type { ProjectStatus } from "@/lib/types";

export function StatusBadge({ status }: { status: ProjectStatus }) {
  return (
    <span
      className={clsx(
        "inline-flex rounded-full border px-2.5 py-1 text-xs font-medium",
        status === "Ready" && "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
        status === "Processing" && "border-brand/30 bg-brand/10 text-cyan-100",
        status === "Draft" && "border-slate-400/20 bg-slate-400/10 text-slate-300"
      )}
    >
      {status}
    </span>
  );
}
