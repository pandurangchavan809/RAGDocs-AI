import { Cpu, Loader2 } from "lucide-react";

import { formatTime } from "../../utils/formatTime";
import Logo from "../ui/Logo";
import Markdown from "./Markdown";
import SourcesBlock from "./SourcesBlock";

export function UserMessage({ text }) {
  return (
    <div className="flex animate-fade-in justify-end">
      <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-zinc-100 px-4 py-2.5 text-[15px] leading-7 text-zinc-900 dark:bg-zinc-800/80 dark:text-zinc-100">
        {text}
      </div>
    </div>
  );
}

export function AssistantMessage({ item, models }) {
  const modelLabel =
    item.model &&
    (models?.find((entry) => entry.id === item.model)?.label ??
      item.model.split(":").pop());

  return (
    <div className="flex animate-fade-in gap-3 sm:gap-4">
      <Logo className="mt-0.5 h-7 w-7 shrink-0" />
      <div className="min-w-0 flex-1 space-y-4">
        <Markdown text={item.answer} />
        {item.sources?.length > 0 && <SourcesBlock sources={item.sources} />}
        <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-zinc-400">
          {modelLabel && (
            <>
              <Cpu className="h-3 w-3" />
              <span className="rounded-md bg-zinc-100 px-1.5 py-0.5 font-mono dark:bg-zinc-800/80">
                {modelLabel}
              </span>
            </>
          )}
          <span>{formatTime(item.created_at)}</span>
        </div>
      </div>
    </div>
  );
}

export function PendingAnswer() {
  return (
    <div className="flex animate-fade-in gap-3 sm:gap-4">
      <Logo className="mt-0.5 h-7 w-7 shrink-0" />
      <div className="flex items-center gap-2 pt-1 text-sm text-zinc-500">
        <Loader2 className="h-4 w-4 animate-spin text-brand-500" />
        <span className="shimmer-text">Searching your documents…</span>
      </div>
    </div>
  );
}
