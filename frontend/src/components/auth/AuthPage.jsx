import NoticeBanner from "../shared/NoticeBanner";
import StatCard from "../shared/StatCard";

function AuthPage({
  authMode,
  busy,
  error,
  form,
  notice,
  onAuthModeChange,
  onFormChange,
  onSubmit,
}) {
  return (
    <main className="flex min-h-screen items-center justify-center overflow-y-auto px-5 py-10">
      <NoticeBanner notice={notice} />

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
              RAGDocs AI is a modern AI-powered document assistant with secure
              login, PDF chat, semantic search, Gemini-powered responses, and
              persistent conversation memory.
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
                onClick={() => onAuthModeChange(mode)}
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

          <form className="space-y-4" onSubmit={onSubmit}>
            {authMode === "register" && (
              <input
                className="field"
                placeholder="Your name"
                value={form.name}
                onChange={(event) => onFormChange("name", event.target.value)}
              />
            )}
            <input
              className="field"
              type="email"
              placeholder="Email"
              value={form.email}
              onChange={(event) => onFormChange("email", event.target.value)}
            />
            <input
              className="field"
              type="password"
              placeholder="Password"
              value={form.password}
              onChange={(event) => onFormChange("password", event.target.value)}
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

export default AuthPage;
