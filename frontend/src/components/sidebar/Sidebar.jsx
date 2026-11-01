import { Eraser, FileText, LogOut, Moon, Sun, Trash2, Upload, X } from "lucide-react";

import { useTheme } from "../../hooks/useTheme";
import { cn } from "../../utils/cn";
import Button from "../ui/Button";
import Logo from "../ui/Logo";

function getInitials(name) {
  const parts = name.trim().split(/\s+/);
  const letters =
    parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : parts[0].slice(0, 2);
  return letters.toUpperCase();
}

function SectionLabel({ children, count }) {
  return (
    <div className="flex items-center justify-between px-1 pb-1.5">
      <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-400">
        {children}
      </p>
      {count > 0 && <span className="text-xs text-zinc-400">{count}</span>}
    </div>
  );
}

function Sidebar({ app, open, onClose, onOpenUpload }) {
  const { dark, toggle } = useTheme();
  const { documents, history, selectedDocs, user } = app;
  const deleteDisabled = app.busy || app.deletingDocs;

  const jumpToMessage = (id) => {
    document.getElementById(`message-${id}`)?.scrollIntoView({ block: "start" });
    onClose();
  };

  return (
    <>
      {open && (
        <div className="fixed inset-0 z-30 bg-zinc-950/40 lg:hidden" onClick={onClose} />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[280px] flex-col border-r border-zinc-200 bg-zinc-50 transition-transform duration-200 lg:static lg:translate-x-0 dark:border-zinc-800/80 dark:bg-zinc-900 lg:dark:bg-zinc-900/50",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex items-center gap-2.5 px-4 pb-3 pt-4">
          <Logo />
          <span className="text-[15px] font-semibold tracking-tight">RAGDocs</span>
          <span className="rounded-md bg-zinc-200/70 px-1.5 py-0.5 text-[10px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
            AI
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="ml-auto lg:hidden"
            onClick={onClose}
            aria-label="Close sidebar"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="px-3">
          <Button
            className="w-full justify-start"
            onClick={app.handleClearHistory}
            disabled={!history.length || app.clearingHistory}
          >
            <Eraser className="h-4 w-4" />
            {app.clearingHistory ? "Clearing…" : "Clear chat"}
          </Button>
        </div>

        <div className="mx-3 mt-3 flex items-center gap-2.5 rounded-xl px-1.5 py-1">
          <span
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-accent-500 text-xs font-semibold text-white"
            aria-hidden="true"
          >
            {getInitials(user.name || user.email)}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium" title={user.name}>
              {user.name}
            </p>
            <p className="truncate text-xs text-zinc-500" title={user.email}>
              {user.email}
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={app.clearSession}
            aria-label="Log out"
            title="Log out"
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>

        <div className="mx-3 mb-3 mt-4 rounded-xl border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-center gap-2 text-sm font-medium">
            <FileText className="h-4 w-4 text-zinc-400" />
            {documents.length === 0
              ? "No documents"
              : documents.length === 1
              ? "1 document"
              : `${documents.length} documents`}
          </div>
          <p className="mt-1 text-xs leading-5 text-zinc-500">
            {documents.length === 0
              ? "Upload a PDF to start."
              : selectedDocs.length
              ? `Chat uses ${selectedDocs.length} selected.`
              : "Chat searches all. Tick files to narrow it."}
          </p>
          <Button
            variant={documents.length ? "secondary" : "primary"}
            size="sm"
            className="mt-3 w-full"
            onClick={onOpenUpload}
          >
            <Upload className="h-3.5 w-3.5" /> Upload PDF
          </Button>
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-3 pb-3">
          {documents.length > 0 && (
            <section>
              <div className="flex items-center justify-between px-1 pb-1.5">
                <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-400">
                  Documents
                </p>
                <button
                  type="button"
                  onClick={app.handleDeleteAllDocuments}
                  disabled={deleteDisabled}
                  className="text-xs text-zinc-500 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:text-red-400"
                >
                  Delete all
                </button>
              </div>
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-start gap-1 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800/70"
                >
                  <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-2.5 px-1.5 py-1.5">
                    <input
                      type="checkbox"
                      checked={selectedDocs.includes(doc.id)}
                      onChange={() => app.toggleDocument(doc.id)}
                      className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-brand-500"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm" title={doc.name}>
                        {doc.name}
                      </span>
                      <span className="block text-xs text-zinc-500">
                        {doc.chunk_count} {doc.chunk_count === 1 ? "chunk" : "chunks"}
                      </span>
                    </span>
                  </label>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="mt-1 hover:text-red-600 dark:hover:text-red-400"
                    onClick={() => app.handleDeleteDocument(doc)}
                    disabled={deleteDisabled}
                    aria-label={`Delete ${doc.name}`}
                    title="Delete document"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </section>
          )}

          {history.length > 0 && (
            <section>
              <SectionLabel count={history.length}>Saved chats</SectionLabel>
              {history.filter((item) => !item.stopped).reverse().map((item) => (
                <button
                  key={item.id || item.created_at}
                  type="button"
                  onClick={() => jumpToMessage(item.id)}
                  className="block w-full truncate rounded-lg px-1.5 py-1.5 text-left text-sm text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800/70 dark:hover:text-zinc-100"
                  title={item.question}
                >
                  {item.question}
                </button>
              ))}
            </section>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-zinc-200 px-4 py-3 text-xs text-zinc-500 dark:border-zinc-800">
          <span>Chats saved to your account</span>
          <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle theme">
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </div>
      </aside>
    </>
  );
}

export default Sidebar;
