import NoticeBanner from "../shared/NoticeBanner";
import ChatPanel from "./ChatPanel";
import PdfSidebar from "./PdfSidebar";

function Dashboard({
  busy,
  clearingHistory,
  documents,
  error,
  history,
  notice,
  question,
  selectedDocs,
  uploading,
  user,
  onAsk,
  onClearHistory,
  onLogout,
  onQuestionChange,
  onToggleDocument,
  onUpload,
}) {
  return (
    <main className="mx-auto flex h-screen max-w-7xl flex-col overflow-hidden px-4 py-4 sm:px-6 sm:py-6">
      <NoticeBanner notice={notice} />

      <header className="panel flex shrink-0 flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-accent">
            RAGDocs AI
          </p>
          <h1 className="mt-2 text-2xl font-bold sm:text-3xl">
            Welcome back, {user.name}
          </h1>
          <p className="mt-2 text-sm text-soft">
            Upload PDFs, choose the documents you want, and chat with grounded
            answers.
          </p>
        </div>
        <button className="button-muted" onClick={onLogout}>
          Logout
        </button>
      </header>

      <section className="grid min-h-0 flex-1 gap-6 pt-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <PdfSidebar
          documents={documents}
          error={error}
          selectedDocs={selectedDocs}
          uploading={uploading}
          onToggleDocument={onToggleDocument}
          onUpload={onUpload}
        />

        <ChatPanel
          busy={busy}
          clearingHistory={clearingHistory}
          history={history}
          question={question}
          onAsk={onAsk}
          onClearHistory={onClearHistory}
          onQuestionChange={onQuestionChange}
        />
      </section>
    </main>
  );
}

export default Dashboard;
