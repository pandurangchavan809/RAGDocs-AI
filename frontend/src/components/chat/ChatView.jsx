import { AlertCircle, ArrowDown, Menu, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import Button from "../ui/Button";
import Composer from "./Composer";
import EmptyState from "./EmptyState";
import { AssistantMessage, PendingAnswer, UserMessage } from "./Messages";
import ModelPicker from "./ModelPicker";

function getDocumentsLabel(total, selected) {
  if (selected) {
    return `${selected} of ${total} documents`;
  }
  return total === 1 ? "1 document" : `All ${total} documents`;
}

function ChatView({ app, onOpenSidebar, onOpenUpload }) {
  const { config, documents, error, history, pendingQuestion, selectedDocs } = app;
  const scrollRef = useRef(null);
  const [pinned, setPinned] = useState(true);
  const hasMessages = history.length > 0 || Boolean(pendingQuestion);

  // Follow new messages only while the user is at the bottom.
  useEffect(() => {
    const element = scrollRef.current;
    if (element && pinned) {
      element.scrollTop = element.scrollHeight;
    }
  }, [history, pendingQuestion, pinned]);

  const handleScroll = () => {
    const element = scrollRef.current;
    if (element) {
      setPinned(element.scrollHeight - element.scrollTop - element.clientHeight < 80);
    }
  };

  const send = (text) => {
    setPinned(true);
    app.askQuestion(text);
  };

  return (
    <main className="flex min-w-0 flex-1 flex-col">
      <header className="flex h-14 shrink-0 items-center gap-1 border-b border-zinc-200/70 px-3 sm:px-4 dark:border-zinc-800/70">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={onOpenSidebar}
          aria-label="Open sidebar"
        >
          <Menu className="h-4 w-4" />
        </Button>
        <ModelPicker config={config} model={app.model} onChange={app.setModel} />
        {documents.length > 0 && (
          <span className="ml-auto hidden max-w-[240px] truncate rounded-full border border-zinc-200 px-2.5 py-1 text-xs text-zinc-500 sm:block dark:border-zinc-800">
            {getDocumentsLabel(documents.length, selectedDocs.length)}
          </span>
        )}
      </header>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="relative flex min-h-0 flex-1 flex-col overflow-y-auto"
      >
        {hasMessages ? (
          <div className="mx-auto w-full max-w-3xl space-y-8 px-4 py-8 sm:px-6">
            {history.map((item) => (
              <article
                key={item.id || item.created_at}
                id={`message-${item.id}`}
                className="scroll-mt-4 space-y-8"
              >
                <UserMessage text={item.question} />
                <AssistantMessage item={item} models={config?.models} />
              </article>
            ))}
            {pendingQuestion && (
              <>
                <UserMessage text={pendingQuestion} />
                <PendingAnswer />
              </>
            )}
          </div>
        ) : (
          <EmptyState
            documentCount={documents.length}
            onPick={send}
            onUpload={onOpenUpload}
          />
        )}
      </div>

      <div className="relative">
        {!pinned && hasMessages && (
          <button
            type="button"
            onClick={() => setPinned(true)}
            className="absolute -top-12 left-1/2 flex h-8 w-8 -translate-x-1/2 items-center justify-center rounded-full border border-zinc-200 bg-white shadow-md dark:border-zinc-700 dark:bg-zinc-900"
            aria-label="Scroll to bottom"
          >
            <ArrowDown className="h-4 w-4" />
          </button>
        )}

        {error && (
          <div className="mx-auto w-full max-w-3xl px-4 pb-3 sm:px-6">
            <div
              role="alert"
              className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <p className="min-w-0 flex-1 break-words">{error}</p>
              <button
                type="button"
                onClick={() => app.setError("")}
                className="shrink-0 hover:opacity-70"
                aria-label="Dismiss error"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        <Composer
          busy={app.busy}
          hasDocuments={documents.length > 0}
          value={app.question}
          onChange={app.setQuestion}
          onSend={send}
        />
      </div>
    </main>
  );
}

export default ChatView;
