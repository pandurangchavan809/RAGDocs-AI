import { ChevronDown, FileText } from "lucide-react";
import { useState } from "react";

import { cn } from "../../utils/cn";

function SourcesBlock({ sources }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-xl border border-zinc-200/80 bg-zinc-50/60 dark:border-zinc-800 dark:bg-zinc-900/40">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left text-[13px]"
        aria-expanded={open}
      >
        <FileText className="h-4 w-4 shrink-0 text-brand-500" />
        <span className="font-medium text-zinc-700 dark:text-zinc-300">
          {sources.length} {sources.length === 1 ? "source" : "sources"}
        </span>
        <ChevronDown
          className={cn(
            "ml-auto h-4 w-4 shrink-0 text-zinc-400 transition-transform",
            open && "rotate-180"
          )}
        />
      </button>

      {open && (
        <ul className="space-y-3 border-t border-zinc-200/80 px-3.5 py-3 dark:border-zinc-800">
          {sources.map((source) => (
            <li
              key={`${source.document_id}-${source.chunk_index}`}
              className="animate-fade-in"
            >
              <p className="flex items-center gap-2 text-[13px] font-medium text-zinc-800 dark:text-zinc-200">
                <span className="min-w-0 truncate">{source.filename}</span>
                {source.page_number && (
                  <span className="shrink-0 font-mono text-[11px] font-normal text-zinc-400">
                    Page {source.page_number}
                  </span>
                )}
              </p>
              <p className="mt-0.5 break-words text-xs leading-5 text-zinc-500">
                {source.excerpt}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default SourcesBlock;
