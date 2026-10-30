import {
  ArrowRight,
  CalendarDays,
  Files,
  GitCompare,
  History,
  ListChecks,
  Quote,
  ScrollText,
  Target,
  Upload,
} from "lucide-react";

import Button from "../ui/Button";
import Logo from "../ui/Logo";

function getSuggestions(documentCount) {
  return [
    { icon: ScrollText, text: "Summarise this document" },
    { icon: ListChecks, text: "What are the key points?" },
    documentCount > 1
      ? { icon: GitCompare, text: "Compare these documents" }
      : { icon: Target, text: "What is the main purpose of this document?" },
    { icon: CalendarDays, text: "List the important dates" },
  ];
}

function EmptyState({ documentCount, onPick, onUpload }) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-4 py-10 sm:px-6">
      <div className="relative mb-6">
        <div className="absolute inset-0 -z-10 scale-150 rounded-full bg-gradient-to-br from-brand-500/25 to-accent-500/25 blur-2xl" />
        <Logo className="h-12 w-12" />
      </div>

      <h1 className="text-center text-2xl font-semibold tracking-tight sm:text-3xl">
        {documentCount ? (
          <>
            What would you like to <span className="text-gradient">know</span>?
          </>
        ) : (
          <>
            Chat with your <span className="text-gradient">documents</span>
          </>
        )}
      </h1>
      <p className="mt-3 max-w-lg text-center text-sm leading-6 text-zinc-500 dark:text-zinc-400">
        {documentCount
          ? "Answers come only from the PDFs you uploaded, with the file and page they came from."
          : "Upload a PDF and ask questions in plain English. Answers come from your documents, with the file and page they came from."}
      </p>

      {documentCount ? (
        <div className="mt-8 grid w-full gap-2.5 sm:grid-cols-2">
          {getSuggestions(documentCount).map(({ icon: Icon, text }) => (
            <button
              key={text}
              type="button"
              onClick={() => onPick(text)}
              className="group flex items-start gap-3 rounded-2xl border border-zinc-200 bg-white p-4 text-left text-sm transition hover:border-zinc-300 hover:shadow-sm dark:border-zinc-800 dark:bg-zinc-900/50 dark:hover:border-zinc-700"
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />
              <span className="flex-1 text-zinc-700 dark:text-zinc-300">{text}</span>
              <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-zinc-300 transition group-hover:translate-x-0.5 group-hover:text-zinc-500" />
            </button>
          ))}
        </div>
      ) : (
        <Button variant="primary" className="mt-8" onClick={onUpload}>
          <Upload className="h-4 w-4" /> Upload a PDF
        </Button>
      )}

      <div className="mt-10 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-zinc-400">
        <span className="flex items-center gap-1.5">
          <Quote className="h-3.5 w-3.5" /> Answers cite sources
        </span>
        <span className="flex items-center gap-1.5">
          <Files className="h-3.5 w-3.5" /> Search across documents
        </span>
        <span className="flex items-center gap-1.5">
          <History className="h-3.5 w-3.5" /> Saved chat memory
        </span>
      </div>
    </div>
  );
}

export default EmptyState;
