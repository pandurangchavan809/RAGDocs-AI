function PdfSidebar({
  documents,
  error,
  selectedDocs,
  uploading,
  onToggleDocument,
  onUpload,
}) {
  return (
    <aside className="panel flex min-h-0 flex-col gap-5 overflow-hidden p-5 sm:p-6">
      <div className="shrink-0">
        <h2 className="text-lg font-semibold">Your PDFs</h2>
        <p className="mt-1 text-sm text-soft">
          Select files to focus the answer. Leave all unchecked to search across
          everything.
        </p>
      </div>

      <label className="button-muted shrink-0 cursor-pointer">
        <input
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={onUpload}
        />
        {uploading ? "Uploading PDF..." : "Upload PDF"}
      </label>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {documents.length === 0 && (
          <div className="rounded-2xl border border-dashed border-line px-4 py-6 text-sm text-soft">
            No PDFs yet. Upload your first document to start the RAG flow.
          </div>
        )}

        {documents.map((doc) => (
          <label
            key={doc.id}
            className="flex cursor-pointer items-start gap-3 rounded-2xl border border-line bg-white/5 p-4"
          >
            <input
              type="checkbox"
              checked={selectedDocs.includes(doc.id)}
              onChange={() => onToggleDocument(doc.id)}
              className="mt-1 h-4 w-4 rounded border-line bg-base text-accent focus:ring-accent"
            />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{doc.name}</p>
              <p className="mt-1 text-xs text-soft">{doc.chunk_count} chunks</p>
            </div>
          </label>
        ))}
      </div>

      {error && (
        <div className="shrink-0 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}
    </aside>
  );
}

export default PdfSidebar;
