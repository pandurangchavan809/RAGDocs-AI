import { ArrowUp, FileText, Loader2 } from "lucide-react";
import { useEffect, useRef } from "react";

function Composer({ busy, hasDocuments, value, onChange, onSend }) {
  const textareaRef = useRef(null);

  useEffect(() => {
    const element = textareaRef.current;
    if (!element) {
      return;
    }
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 220)}px`;
  }, [value]);

  useEffect(() => {
    if (hasDocuments) {
      textareaRef.current?.focus();
    }
  }, [hasDocuments]);

  const canSend = hasDocuments && !busy && value.trim().length > 0;

  const submit = () => {
    if (canSend) {
      onSend(value);
    }
  };

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-4 sm:px-6">
      <div className="rounded-2xl border border-zinc-200 bg-white shadow-[0_2px_16px_-6px_rgb(0_0_0/0.12)] transition-colors focus-within:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900 dark:focus-within:border-zinc-600">
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          disabled={!hasDocuments}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (
              event.key === "Enter" &&
              !event.shiftKey &&
              !event.nativeEvent.isComposing
            ) {
              event.preventDefault();
              submit();
            }
          }}
          placeholder={
            hasDocuments
              ? "Ask anything about your documents…"
              : "Upload a PDF to start asking questions"
          }
          className="block max-h-[220px] w-full resize-none bg-transparent px-4 pb-1 pt-3.5 text-[15px] leading-6 outline-none placeholder:text-zinc-400 disabled:cursor-not-allowed"
          aria-label="Message"
        />
        <div className="flex items-center gap-2 px-3 pb-2.5">
          <span className="flex items-center gap-1 text-[11px] text-zinc-400">
            <FileText className="h-3 w-3" /> Answers from your documents
          </span>
          <button
            type="button"
            onClick={submit}
            disabled={!canSend}
            className="ml-auto flex h-8 w-8 items-center justify-center rounded-full bg-zinc-900 text-white transition hover:bg-zinc-700 disabled:cursor-not-allowed disabled:bg-zinc-200 disabled:text-zinc-400 dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-200 dark:disabled:bg-zinc-800 dark:disabled:text-zinc-600"
            aria-label="Send message"
          >
            {busy ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ArrowUp className="h-4 w-4" strokeWidth={2.5} />
            )}
          </button>
        </div>
      </div>
      <p className="mt-2 text-center text-[11px] text-zinc-400">
        RAGDocs can make mistakes. Check answers against the sources.
      </p>
    </div>
  );
}

export default Composer;
