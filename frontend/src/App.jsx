import { useEffect, useRef, useState } from "react";
import api, { setAuthToken } from "./api";

const emptyForm = { name: "", email: "", password: "" };
const emptyNotice = { message: "", type: "" };
const TOKEN_KEY = "ragdocs_token";
const USER_KEY = "ragdocs_user";

function formatTime(value) {
  return new Date(value).toLocaleString();
}

function App() {
  const [token, setToken] = useState(localStorage.getItem(TOKEN_KEY) || "");
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem(USER_KEY);
    return saved ? JSON.parse(saved) : null;
  });
  const [authMode, setAuthMode] = useState("login");
  const [form, setForm] = useState(emptyForm);
  const [documents, setDocuments] = useState([]);
  const [selectedDocs, setSelectedDocs] = useState([]);
  const [history, setHistory] = useState([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [clearingHistory, setClearingHistory] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(emptyNotice);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    setAuthToken(token);
  }, [token]);

  useEffect(() => {
    if (!token) {
      return;
    }
    loadDashboard();
  }, [token]);

  useEffect(() => {
    if (!notice.message) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      setNotice(emptyNotice);
    }, 2800);

    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: history.length > 1 ? "smooth" : "auto",
      block: "end",
    });
  }, [history]);

  async function loadDashboard() {
    try {
      const [docsRes, historyRes] = await Promise.all([
        api.get("/documents"),
        api.get("/chat/history"),
      ]);
      setDocuments(docsRes.data);
      setHistory(historyRes.data);
    } catch (err) {
      handleError(err, "Could not load your workspace.");
    }
  }

  function saveSession(nextToken, nextUser) {
    setToken(nextToken);
    setUser(nextUser);
    localStorage.setItem(TOKEN_KEY, nextToken);
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
    setError("");
  }

  function clearSession() {
    setToken("");
    setUser(null);
    setDocuments([]);
    setSelectedDocs([]);
    setHistory([]);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setAuthToken("");
  }

  function handleError(err, fallbackMessage) {
    const message = err?.response?.data?.error || fallbackMessage;
    setError(message);
  }

  function showNotice(message, type = "success") {
    setNotice({ message, type });
  }

  async function handleAuthSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const endpoint = authMode === "login" ? "/auth/login" : "/auth/register";
      const payload =
        authMode === "login"
          ? { email: form.email, password: form.password }
          : form;
      const response = await api.post(endpoint, payload);

      if (authMode === "register") {
        setAuthMode("login");
        setForm({
          ...emptyForm,
          email: response.data.user?.email || form.email,
        });
        showNotice(
          response.data.message || "Account created successfully. Please log in."
        );
      } else {
        saveSession(response.data.token, response.data.user);
        setForm(emptyForm);
      }
    } catch (err) {
      handleError(err, `Could not ${authMode}.`);
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setUploading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      await api.post("/documents/upload", formData);
      event.target.value = "";
      showNotice("PDF uploaded successfully.");
      await loadDashboard();
    } catch (err) {
      handleError(err, "Could not upload this PDF.");
    } finally {
      setUploading(false);
    }
  }

  async function handleClearHistory() {
    if (!history.length || clearingHistory) {
      return;
    }

    const confirmed = window.confirm(
      "Clear only the chat history? Uploaded PDFs will stay safe."
    );
    if (!confirmed) {
      return;
    }

    setClearingHistory(true);
    setError("");
    try {
      const response = await api.delete("/chat/history");
      setHistory([]);
      showNotice(response.data.message || "Chat history cleared successfully.");
    } catch (err) {
      handleError(err, "Could not clear chat history.");
    } finally {
      setClearingHistory(false);
    }
  }

  function toggleDocument(id) {
    setSelectedDocs((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id]
    );
  }

  async function handleAsk(event) {
    event.preventDefault();
    if (!question.trim()) {
      return;
    }

    const pendingQuestion = question.trim();
    setBusy(true);
    setError("");
    setQuestion("");

    try {
      const response = await api.post("/chat", {
        question: pendingQuestion,
        document_ids: selectedDocs,
      });

      setHistory((current) => [
        ...current,
        {
          id: response.data.message_id,
          question: pendingQuestion,
          answer: response.data.answer,
          sources: response.data.sources,
          created_at: new Date().toISOString(),
        },
      ]);
    } catch (err) {
      setQuestion(pendingQuestion);
      handleError(err, "Could not get an answer right now.");
    } finally {
      setBusy(false);
    }
  }

  const noticeBanner = notice.message ? (
    <div
      className={`fixed right-5 top-5 z-50 rounded-2xl border px-4 py-3 text-sm shadow-glow ${
        notice.type === "success"
          ? "border-emerald-400/30 bg-emerald-500/15 text-emerald-100"
          : "border-sky-400/30 bg-sky-500/15 text-sky-100"
      }`}
    >
      {notice.message}
    </div>
  ) : null;

  if (!token || !user) {
    return (
      <main className="flex min-h-screen items-center justify-center overflow-y-auto px-5 py-10">
        {noticeBanner}

        <section className="panel grid w-full max-w-5xl overflow-hidden lg:grid-cols-[1.08fr_0.92fr]">
          <div className="flex flex-col justify-between gap-8 border-b border-line p-8 lg:border-b-0 lg:border-r lg:p-10">
            <div className="space-y-5">
              <div className="inline-flex rounded-full border border-sky-300/30 bg-sky-400/10 px-3 py-1 text-xs font-semibold text-sky-200">
                RAGDocs AI
              </div>
              <p className="text-xs uppercase tracking-[0.3em] text-accent">
                RAG-Based Intelligent PDF Assistant
              </p>
              <h1 className="max-w-xl text-4xl font-bold leading-tight text-white sm:text-5xl">
                Ask your PDFs simple questions and get grounded answers.
              </h1>
              <p className="max-w-xl text-base font-medium leading-8 text-sky-100">
                RAGDocs AI is a modern AI-powered document assistant with secure login, PDF chat, semantic search, Gemini-powered responses, and persistent conversation memory — Made with ❤️
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <StatCard title="Auth" value="JWT Login" />
              <StatCard title="RAG" value="Chroma + Gemini" />
              <StatCard title="Memory" value="Saved Chats" />
            </div>
          </div>

          <div className="p-8 lg:p-10">
            <div className="mb-6 flex rounded-2xl border border-line bg-white/5 p-1">
              {["login", "register"].map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => setAuthMode(mode)}
                  className={`flex-1 rounded-xl px-4 py-2 text-sm font-medium transition ${
                    authMode === mode
                      ? "bg-accent text-slate-950"
                      : "text-soft hover:text-white"
                  }`}
                >
                  {mode === "login" ? "Login" : "Register"}
                </button>
              ))}
            </div>

            <form className="space-y-4" onSubmit={handleAuthSubmit}>
              {authMode === "register" && (
                <input
                  className="field"
                  placeholder="Your name"
                  value={form.name}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      name: event.target.value,
                    }))
                  }
                />
              )}
              <input
                className="field"
                type="email"
                placeholder="Email"
                value={form.email}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    email: event.target.value,
                  }))
                }
              />
              <input
                className="field"
                type="password"
                placeholder="Password"
                value={form.password}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    password: event.target.value,
                  }))
                }
              />
              {error && (
                <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                  {error}
                </div>
              )}
              <button className="button-primary w-full" disabled={busy}>
                {busy
                  ? "Please wait..."
                  : authMode === "login"
                  ? "Enter Workspace"
                  : "Create Account"}
              </button>
            </form>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto flex h-screen max-w-7xl flex-col overflow-hidden px-4 py-4 sm:px-6 sm:py-6">
      {noticeBanner}

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
        <button className="button-muted" onClick={clearSession}>
          Logout
        </button>
      </header>

      <section className="grid min-h-0 flex-1 gap-6 pt-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="panel flex min-h-0 flex-col gap-5 overflow-hidden p-5 sm:p-6">
          <div className="shrink-0">
            <h2 className="text-lg font-semibold">Your PDFs</h2>
            <p className="mt-1 text-sm text-soft">
              Select files to focus the answer. Leave all unchecked to search
              across everything.
            </p>
          </div>

          <label className="button-muted shrink-0 cursor-pointer">
            <input
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={handleUpload}
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
                  onChange={() => toggleDocument(doc.id)}
                  className="mt-1 h-4 w-4 rounded border-line bg-base text-accent focus:ring-accent"
                />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{doc.name}</p>
                  <p className="mt-1 text-xs text-soft">
                    {doc.chunk_count} chunks
                  </p>
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
                onClick={handleClearHistory}
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
                    Upload at least one PDF, then ask a question. RAGDocs AI
                    will retrieve relevant chunks and answer from those sources.
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
                                {source.page_number ? ` • Page ${source.page_number}` : ""}
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

          <form
            className="mt-5 shrink-0 border-t border-line pt-4"
            onSubmit={handleAsk}
          >
            <div className="flex flex-col gap-3 sm:flex-row">
              <input
                className="field flex-1"
                placeholder="Ask a question about your documents..."
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
              />
              <button className="button-primary sm:w-40" disabled={busy}>
                {busy ? "Thinking..." : "Ask"}
              </button>
            </div>
          </form>
        </section>
      </section>
    </main>
  );
}

function StatCard({ title, value }) {
  return (
    <div className="rounded-3xl border border-line bg-white/5 p-4">
      <p className="text-xs uppercase tracking-[0.25em] text-soft">{title}</p>
      <p className="mt-3 text-lg font-semibold">{value}</p>
    </div>
  );
}

export default App;
