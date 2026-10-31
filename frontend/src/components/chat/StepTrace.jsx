import {
  Binary,
  Check,
  ChevronDown,
  Loader2,
  Search,
  Send,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { useState } from "react";

import { cn } from "../../utils/cn";

function formatDuration(ms) {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

function getStepIcon(id) {
  if (id === "embed") {
    return Binary;
  }
  return id === "retrieve" ? Search : Send;
}

function StatusIcon({ status }) {
  if (status === "running") {
    return <Loader2 className="h-3.5 w-3.5 animate-spin text-brand-500" />;
  }
  if (status === "error") {
    return <TriangleAlert className="h-3.5 w-3.5 text-amber-500" />;
  }
  return <Check className="h-3.5 w-3.5 text-emerald-500" />;
}

function StepTrace({ steps, live, stopped, totalMs }) {
  const [open, setOpen] = useState(null);

  if (!steps?.length) {
    return live ? (
      <div className="flex items-center gap-2 pt-1 text-sm text-zinc-500">
        <Loader2 className="h-4 w-4 animate-spin text-brand-500" />
        <span className="shimmer-text">Preparing your documents…</span>
      </div>
    ) : null;
  }

  const running = steps.find((step) => step.status === "running");
  // Expanded while answering, collapsed afterwards, unless the user toggled it.
  const expanded = open ?? live;

  return (
    <div className="rounded-xl border border-zinc-200/80 bg-zinc-50/60 dark:border-zinc-800 dark:bg-zinc-900/40">
      <button
        type="button"
        onClick={() => setOpen(!expanded)}
        className="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left text-[13px]"
        aria-expanded={expanded}
      >
        {running ? (
          <>
            <Loader2 className="h-4 w-4 shrink-0 animate-spin text-brand-500" />
            <span className="shimmer-text font-medium text-zinc-700 dark:text-zinc-300">
              {running.label}…
            </span>
          </>
        ) : (
          <>
            <Sparkles className="h-4 w-4 shrink-0 text-brand-500" />
            <span className="font-medium text-zinc-700 dark:text-zinc-300">
              {live
                ? "Writing answer…"
                : stopped
                ? "Stopped"
                : totalMs !== undefined
                ? `Completed in ${formatDuration(totalMs)}`
                : "Completed"}
            </span>
            <span className="text-zinc-400">·</span>
            <span className="text-zinc-500">
              {steps.length} {steps.length === 1 ? "step" : "steps"}
            </span>
          </>
        )}
        <ChevronDown
          className={cn(
            "ml-auto h-4 w-4 shrink-0 text-zinc-400 transition-transform",
            expanded && "rotate-180"
          )}
        />
      </button>

      {expanded && (
        <ol className="space-y-0.5 border-t border-zinc-200/80 px-3.5 py-3 dark:border-zinc-800">
          {steps.map((step, index) => {
            const Icon = getStepIcon(step.id);
            return (
              <li key={step.id} className="relative flex animate-fade-in gap-3 pb-2">
                {index < steps.length - 1 && (
                  <span
                    className="absolute bottom-0 left-[13px] top-7 w-px bg-zinc-200 dark:bg-zinc-800"
                    aria-hidden="true"
                  />
                )}
                <span className="relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900">
                  <Icon className="h-3.5 w-3.5 text-zinc-500 dark:text-zinc-400" />
                </span>
                <div className="min-w-0 flex-1 pt-1">
                  <div className="flex items-center gap-2 text-[13px]">
                    <StatusIcon status={step.status} />
                    <span className="min-w-0 truncate font-medium text-zinc-800 dark:text-zinc-200">
                      {step.label}
                    </span>
                    {step.duration_ms !== undefined && (
                      <span className="ml-auto shrink-0 font-mono text-[11px] text-zinc-400">
                        {formatDuration(step.duration_ms)}
                      </span>
                    )}
                  </div>
                  {step.detail && (
                    <p
                      className={cn(
                        "mt-0.5 break-words text-xs leading-5",
                        step.status === "error"
                          ? "text-amber-600 dark:text-amber-400"
                          : "text-zinc-500"
                      )}
                    >
                      {step.detail}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

export default StepTrace;
