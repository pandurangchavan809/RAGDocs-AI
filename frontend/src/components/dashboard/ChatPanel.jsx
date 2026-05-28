import { useEffect, useRef } from "react";

import { formatTime } from "../../utils/formatTime";

function ChatPanel({
  busy,
  clearingHistory,
  history,
  question,
  onAsk,
  onClearHistory,
  onQuestionChange,
}) {
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: history.length > 1 ? "smooth" : "auto",
      block: "end",
    });
  }, [history]);

  return (
    <section className="panel flex min-h-0 flex-col overflow-hidden p-4 sm:p-6">
      <div className="mb-4 flex shrink-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold">Chat</h2>
          <p className="mt-1 text-sm text-soft">
            Ask concise questions like "summarize chapter 2" or "compare the
            key ideas."
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="button-muted px-3 py-2 text-xs"
            onClick={onClearHistory}
            disabled={!history.length || clearingHistory}
          >
            {clearingHistory ? "Clearing..." : "Clear Chat"}
          </button>
          <div className="rounded-full border border-line px-3 py-2 text-xs text-soft">
            {history.length} messages
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {history.length === 0 ? (
          <div className="flex h-full min-h-[320px] items-center justify-center rounded-3xl border border-dashed border-line bg-white/5 text-center">
            <div className="max-w-sm space-y-3 px-6">
              <h3 className="text-xl font-semibold">Your PDF assistant is ready.</h3>
              <p className="text-sm leading-7 text-soft">
                Upload at least one PDF, then ask a question. RAGDocs AI will
                retrieve relevant chunks and answer from those sources.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {history.map((item) => (
              <article key={item.id || item.created_at} className="space-y-3">
                <div className="ml-auto max-w-3xl rounded-3xl rounded-br-md bg-accent px-4 py-3 text-sm text-slate-950">
                  {item.question}
                </div>

                <div className="max-w-4xl rounded-3xl rounded-bl-md border border-line bg-white/5 px-4 py-4">
                  <p className="whitespace-pre-wrap text-sm leading-7 text-slate-100">
                    {item.answer}
                  </p>

                  {item.sources?.length > 0 && (
                    <div className="mt-4 grid gap-3">
                      {item.sources.map((source) => (
                        <div
                          key={`${source.document_id}-${source.chunk_index}`}
                          className="rounded-2xl border border-line bg-base/60 p-3"
                        >
                          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">
                            {source.filename}
                            {source.page_number
                              ? ` • Page ${source.page_number}`
                              : ""}
                          </p>
                          <p className="mt-2 text-sm text-soft">
                            {source.excerpt}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}

                  <p className="mt-4 text-xs text-soft">
                    {formatTime(item.created_at)}
                  </p>
                </div>
              </article>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      <form className="mt-5 shrink-0 border-t border-line pt-4" onSubmit={onAsk}>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            className="field flex-1"
            placeholder="Ask a question about your documents..."
            value={question}
            onChange={(event) => onQuestionChange(event.target.value)}
          />
          <button className="button-primary sm:w-40" disabled={busy}>
            {busy ? "Thinking..." : "Ask"}
          </button>
        </div>
      </form>
    </section>
  );
}

export default ChatPanel;
