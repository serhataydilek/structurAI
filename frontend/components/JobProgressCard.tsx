import type { JobProgress } from "@/lib/types";

function formatDuration(seconds?: number | null) {
  if (!seconds || seconds < 1) return "0 sec";
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 1) return `${remainingSeconds} sec`;
  if (minutes < 60) return `${minutes} min${remainingSeconds ? ` ${remainingSeconds} sec` : ""}`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours} hr${remainingMinutes ? ` ${remainingMinutes} min` : ""}`;
}

function statusClass(status?: string) {
  if (status === "completed") return "border-emerald-300/20 bg-emerald-300/10 text-emerald-100";
  if (status === "failed") return "border-red-400/30 bg-red-400/10 text-red-100";
  if (status === "running") return "border-brand/30 bg-brand/10 text-cyan-100";
  return "border-white/10 bg-white/[0.03] text-slate-300";
}

export function JobProgressCard({ progress, title, unknownEtaMessage }: { progress?: JobProgress | null; title: string; unknownEtaMessage?: string }) {
  const percent = progress?.progressPercent;
  const hasStarted = Boolean(progress?.startedAt);
  const processedTotal =
    typeof progress?.processedItems === "number" && typeof progress?.totalItems === "number"
      ? `${progress.processedItems}/${progress.totalItems}`
      : null;
  const etaText =
    progress?.status === "running"
      ? progress.etaSeconds != null
        ? `Estimated time remaining: ~${formatDuration(progress.etaSeconds)}`
        : unknownEtaMessage ?? "ETA unknown for this stage."
      : "ETA not applicable.";

  return (
    <div className={`rounded-lg border p-4 ${statusClass(progress?.status)}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">{title}</p>
          <p className="mt-1 text-sm">{progress?.currentStepLabel ?? "Not run yet."}</p>
        </div>
        <span className="rounded-md border border-current/25 px-2.5 py-1 text-xs font-semibold capitalize">
          {progress?.status ?? "pending"}
        </span>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-900">
        <div className="h-full rounded-full bg-brand transition-all duration-700" style={{ width: `${percent ?? 0}%` }} />
      </div>
      <div className="mt-3 grid gap-2 text-xs text-slate-300 sm:grid-cols-3">
        <p>Progress: {percent == null ? "Stage-based / unknown" : `${percent}%`}</p>
        <p>Elapsed: {hasStarted ? formatDuration(progress?.elapsedSeconds) : "Not run yet"}</p>
        <p>{etaText}</p>
        {processedTotal && <p>Items: {processedTotal}</p>}
        {progress?.currentStage && <p className="sm:col-span-2">Stage: {progress.currentStage.replaceAll("_", " ")}</p>}
      </div>
      {(progress?.logTail?.length ?? 0) > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-semibold text-slate-200">Log tail</summary>
          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded border border-white/10 bg-slate-950/70 p-3 text-xs leading-5 text-slate-300">
            {progress?.logTail.join("\n")}
          </pre>
        </details>
      )}
      {(progress?.warnings?.length ?? 0) > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-semibold text-amber-100">Warnings</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs">
            {progress?.warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        </details>
      )}
      {(progress?.errors?.length ?? 0) > 0 && (
        <details className="mt-3" open>
          <summary className="cursor-pointer text-xs font-semibold text-red-100">Errors</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs">
            {progress?.errors.map((error) => <li key={error}>{error}</li>)}
          </ul>
        </details>
      )}
    </div>
  );
}
