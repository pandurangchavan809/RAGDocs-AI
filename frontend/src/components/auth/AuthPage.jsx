import { Eye, EyeOff, KeyRound, Loader2, Moon, Sun } from "lucide-react";
import { useState } from "react";

import { DEMO_ACCOUNT } from "../../constants/app";
import { useTheme } from "../../hooks/useTheme";
import { cn } from "../../utils/cn";
import NoticeBanner from "../shared/NoticeBanner";
import Button from "../ui/Button";
import Logo from "../ui/Logo";

const inputClass =
  "h-10 w-full rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none transition-colors placeholder:text-zinc-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 dark:border-zinc-800 dark:bg-zinc-900";

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
        {label}
      </span>
      {children}
    </label>
  );
}

function AuthPage({
  authMode,
  busy,
  error,
  form,
  notice,
  onAuthModeChange,
  onDemoLogin,
  onFormChange,
  onSubmit,
}) {
  const { dark, toggle } = useTheme();
  const [showPassword, setShowPassword] = useState(false);
  const isLogin = authMode === "login";

  return (
    <main className="flex min-h-full items-center justify-center px-4 py-10">
      <NoticeBanner notice={notice} />

      <Button
        variant="ghost"
        size="icon"
        className="fixed right-4 top-4"
        onClick={toggle}
        aria-label="Toggle theme"
      >
        {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </Button>

      <div className="w-full max-w-sm animate-fade-in">
        <div className="flex flex-col items-center text-center">
          <Logo className="h-10 w-10" />
          <h1 className="mt-4 text-xl font-semibold tracking-tight">
            {isLogin ? "Log in to RAGDocs" : "Create your account"}
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            Chat with your PDFs and get answers with sources.
          </p>
        </div>

        <div className="mt-6 grid grid-cols-2 rounded-xl bg-zinc-100 p-1 text-sm dark:bg-zinc-900">
          {["login", "register"].map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => onAuthModeChange(mode)}
              className={cn(
                "h-8 rounded-lg font-medium transition-colors",
                authMode === mode
                  ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-800 dark:text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
              )}
            >
              {mode === "login" ? "Log in" : "Sign up"}
            </button>
          ))}
        </div>

        <form onSubmit={onSubmit} className="mt-5 space-y-3">
          {!isLogin && (
            <Field label="Name">
              <input
                className={inputClass}
                autoComplete="name"
                placeholder="Your name"
                value={form.name}
                onChange={(event) => onFormChange("name", event.target.value)}
                required
              />
            </Field>
          )}
          <Field label="Email">
            <input
              className={inputClass}
              type="email"
              autoComplete={isLogin ? "username" : "email"}
              placeholder="you@example.com"
              value={form.email}
              onChange={(event) => onFormChange("email", event.target.value)}
              required
            />
          </Field>
          <Field label="Password">
            <div className="relative">
              <input
                className={cn(inputClass, "pr-10")}
                type={showPassword ? "text" : "password"}
                autoComplete={isLogin ? "current-password" : "new-password"}
                placeholder="Your password"
                value={form.password}
                onChange={(event) => onFormChange("password", event.target.value)}
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((current) => !current)}
                className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </Field>

          {error && (
            <p
              role="alert"
              className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600 dark:bg-red-500/10 dark:text-red-400"
            >
              {error}
            </p>
          )}

          <Button type="submit" variant="primary" className="w-full" disabled={busy}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            {isLogin ? "Log in" : "Create account"}
          </Button>
        </form>

        <div className="mt-6 rounded-xl border border-dashed border-zinc-300 p-4 dark:border-zinc-700">
          <div className="flex items-center gap-2 text-sm font-medium">
            <KeyRound className="h-4 w-4 text-brand-500" /> Demo account
          </div>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-zinc-500">Email</dt>
            <dd className="break-all font-mono">{DEMO_ACCOUNT.email}</dd>
            <dt className="text-zinc-500">Password</dt>
            <dd className="break-all font-mono">{DEMO_ACCOUNT.password}</dd>
          </dl>
          <Button size="sm" className="mt-3 w-full" onClick={onDemoLogin} disabled={busy}>
            Log in with demo account
          </Button>
          <p className="mt-2 text-xs leading-5 text-zinc-500">
            Shared account. Other visitors can see what you upload, so don't use private files.
          </p>
        </div>
      </div>
    </main>
  );
}

export default AuthPage;
