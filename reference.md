# UI Reference: Bring the DataPilot AI Interface to RAGDocs AI

This file is a handoff for a Claude Code session working in the **RAGDocs AI repo**. That session
cannot see the DataPilot repo, so everything it needs is here, including the real source code.

- **Section 1** is the prompt to paste.
- **Sections 2 to 7** are the design rules and how they map to RAGDocs.
- **Section 8** is the DataPilot source code to copy from.

---

## 1. Prompt to paste into the RAGDocs chat

Put this file in the RAGDocs repo root, then paste:

```text
Redesign the RAGDocs AI frontend to match the UI described in reference.md. Read all of it first.

RAGDocs AI is a RAG PDF assistant (React frontend, Flask backend, LangChain, Gemini API, ChromaDB,
MySQL, JWT login, saved chat memory, multi-document chat).

Rules:
1. Change the frontend's look and layout only. Keep all existing features, API calls, JWT login and
   saved chats working. Do not change RAG, retrieval, database or auth logic.
2. Inspect the repo before editing: read the frontend package.json, styling setup, routes, API
   client, and the backend's chat and document endpoints. Then give me a short plan: which screens
   change, which packages get added, and any backend change you think is needed.
3. Copy the design from section 8 as closely as possible: same layout, spacing, colours, components
   and behaviour. Replace DataPilot's content with RAGDocs content using the mapping in section 5.
4. Do not show anything the backend doesn't really do. No fake models, steps, sources or timings.
   Where the backend lacks something, follow section 6: hide that part of the UI, or list the small
   backend addition in your plan and wait for my approval.
5. Give RAGDocs its own name and its own simple logo. Do not reuse the DataPilot name or logo mark.
6. Support light and dark mode and phone widths, as in the reference.
7. When finished, run the frontend build and go through the checklist in section 7. Tell me what you
   verified and what you could not.
```

---

## 2. What this UI style is called

It has no product name and no template or UI kit behind it. It is custom-built with Tailwind.
To describe it, say:

> **A ChatGPT-style minimal AI chat interface:** neutral zinc surfaces, one indigo-to-cyan accent,
> a collapsible "Reasoned in X s" step trace, and a grouped model picker with an Auto option.

The useful search terms are *conversational AI chat UI*, *minimal neutral dark UI* and
*reasoning trace*.

---

## 3. Tech stack

| Purpose | Library |
|---|---|
| Framework | React 19, TypeScript 5.8, Vite 6 |
| Styling | Tailwind CSS v4 through `@tailwindcss/vite`, with no component library |
| Icons | `lucide-react` |
| State | `zustand` |
| Markdown answers | `react-markdown` + `remark-gfm` |
| Class names | `clsx` |
| Fonts | Inter (UI), JetBrains Mono (code and technical labels), from Google Fonts |

If RAGDocs uses something else, such as JavaScript or Tailwind v3, keep its setup and translate. The
`@theme` values in section 8 become `tailwind.config.js` entries on v3. Don't migrate the project just
for this.

The `@/` import prefix is a Vite alias for `src/`. `cn()` is `clsx` re-exported from `src/utils.ts`.

---

## 4. Design rules

**Layout**
- Full-height two-column shell: a 280px sidebar and a flexible main column. Below the `lg`
  breakpoint, the sidebar becomes a slide-in drawer with a dark overlay.
- Main column: a 56px header (`h-14`) with the model picker on the left, a scrolling message area,
  and the composer pinned at the bottom.
- Messages and composer share one centred column: `max-w-3xl`.

**Colour**
- Neutrals are Tailwind `zinc`. Light page: white. Dark page: `zinc-950`.
- There is one accent: brand indigo (`#6366f1`) with cyan (`#06b6d4`) in gradients. Use it sparingly,
  for small icons, badges, the selected tick and one highlighted word in the headline.
- Green is for success and "connected", amber for recoverable issues, red for errors. Never use
  these as decoration.

**Shape and type**
- Radius: `rounded-xl` for buttons and cards, `rounded-2xl` for the composer, popovers, dialogs and
  suggestion cards, `rounded-full` for the send button and avatar.
- Thin 1px borders and very few shadows. Popovers use `shadow-xl`.
- Body text 15px with `leading-7`. Secondary text 13px or 12px. Section labels 11px, uppercase,
  `tracking-wide`, `zinc-400`.
- Small `animate-fade-in` on new content (0.25s). No bouncing or large motion.

**Signature components (these make it look like this UI, so keep them)**
1. **Model picker:** a borderless header button that opens a popover: Auto with a "Recommended"
   badge first, then models grouped under uppercase provider labels, with a tick on the selection.
2. **Step trace:** a card above each answer. While streaming, it is expanded with a live spinner and
   shimmering label. Afterwards it collapses to "Reasoned in 17.6 s · 7 steps".
3. **Composer:** a rounded card with an auto-growing textarea, a small status label at the bottom
   left and a round send button that turns into a stop button while generating.
4. **Messages:** the user's message is a right-aligned zinc bubble. The assistant's answer has no
   bubble: logo on the left, Markdown text on the page, and a blinking cursor while streaming.
5. **Empty state:** a logo with a soft gradient glow, a headline with one gradient word, a 2x2 grid
   of suggestion cards and one small row of trust labels.
6. **User row:** a gradient circle with two initials, name, email and a log-out icon, under New chat.

---

## 5. Mapping from DataPilot to RAGDocs

| DataPilot | RAGDocs |
|---|---|
| "Connect a database" | Upload PDFs |
| Connection card in the sidebar | Documents card: count, upload button, and which documents the chat uses |
| Schema explorer (tables and columns) | Document list: file name, pages, delete, select for multi-document chat |
| "Chats stay in this tab only" | **Saved chats list** in the sidebar, because RAGDocs keeps chat memory |
| Connection pill in the header | Selected documents pill, such as "3 documents" |
| Result table and SQL block under the answer | **Sources block:** collapsible, same card style as `AgentTrace`, showing file name, page and matched text |
| Chart view | Not needed |
| "Read-only" label in the composer | "Answers from your documents" |
| "Verify important numbers against the SQL shown" | "RAGDocs can make mistakes. Check answers against the sources." |
| Composer disabled until connected | Disabled until at least one document is ready |
| Connection dialog | Upload dialog using the same `Dialog`, with a drag-and-drop area |
| Example questions about GDP | "Summarise this document", "What are the key points?", "Compare these documents", "List the important dates" |
| "Talk to your data in plain English" | "Chat with your documents" (gradient on one word) |
| Trust row: read-only, self-correcting, charts | Only true labels, such as "Answers cite sources" and "Search across documents", if they are true |

---

## 6. Where the backend may need checking

DataPilot's UI relies on things RAGDocs may not have. Check each one in the RAGDocs code.

| UI feature | What it needs | If it's missing |
|---|---|---|
| **Model picker** | A list of models from the server, plus the chat request accepting a model id. DataPilot returns it from `GET /api/config` in the shape below. | Small backend addition; ask first. Never show a model the backend can't call. If only one model exists, show it as a plain label with no dropdown. |
| **Auto option** | Backend default when no model is sent, plus optional fallback | Describe it accurately. Use "Default model" if there is no fallback. |
| **Live step trace** | The backend sending progress as it works (Server-Sent Events) | Don't fake steps with timers. Either add streaming (ask first) or show a simple "Searching your documents…" spinner, with no timings or step count. |
| **Token-by-token answer** | A streaming response | Render the full answer when it arrives, without the cursor. |
| **Sources block** | Retrieved chunks returned with the answer (file, page, text) | Often a small change, since LangChain already has the chunks. Ask first, or hide the block. |
| **Trace step names** | Real pipeline stages, such as searching documents, then writing the answer | Name only stages that really happen. |

Model list shape used by the picker:

```ts
interface ModelInfo {
  id: string;             // "gemini:gemini-3.5-flash" (provider:model), sent back with each chat
  label: string;          // display name
  name: string;           // raw model id, shown as the subtitle
  provider: string;       // "gemini"
  provider_label: string; // "Google Gemini", used as the group heading
  roles: string[];        // e.g. ["primary"]; drives the badge
}
```

In the picker, change the Auto subtitle to whatever RAGDocs Auto really does. `useApp` in the code
below is DataPilot's zustand store; use the RAGDocs state instead, or add a small store.

Check that the model names you list are the ones RAGDocs really uses. The names in this file are examples.

---

## 7. Finish checklist

- [ ] Frontend build passes with no type errors.
- [ ] Log in, sign up and log out still work, and tokens are handled as before.
- [ ] Upload, delete and multi-document selection still work.
- [ ] Saved chats still load and appear in the sidebar.
- [ ] A question gets a correct answer with real sources.
- [ ] The model picker shows only models that work, and the chosen one is really used.
- [ ] Light and dark mode both look right, including the login page and popovers.
- [ ] At phone width: the sidebar is a drawer and there is no sideways scrolling.
- [ ] No "DataPilot", SQL, database or schema wording remains in the UI.
- [ ] Nothing on screen is fake: every model, step, time and source comes from the backend.

---

## 8. Source code to copy from

This is the real DataPilot code. Copy the classes and structure, and swap the content using section 5.

### Page setup: `index.html` (theme script and fonts)

The small inline script sets dark mode before the page paints, which prevents a white flash.

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="DataPilot AI: ask your database questions in plain English." />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
    <title>DataPilot AI</title>
    <script>
      try {
        const t = localStorage.getItem("dp-theme");
        if (t === "dark" || (!t && matchMedia("(prefers-color-scheme: dark)").matches)) document.documentElement.classList.add("dark");
      } catch {}
    </script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

### Design tokens and global styles: `src/index.css`

Skip the "Chart tokens" block at the end if RAGDocs has no charts.

```css
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));

@theme {
  --font-sans: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;

  --color-brand-50: #eef2ff;
  --color-brand-100: #e0e7ff;
  --color-brand-400: #818cf8;
  --color-brand-500: #6366f1;
  --color-brand-600: #4f46e5;
  --color-accent-500: #06b6d4;

  --animate-fade-in: fade-in 0.25s ease-out both;
  --animate-shimmer: shimmer 1.6s linear infinite;
  --animate-blink: blink 1s steps(2, start) infinite;

  @keyframes fade-in {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: none; }
  }
  @keyframes shimmer {
    from { background-position: -200% 0; }
    to { background-position: 200% 0; }
  }
  @keyframes blink {
    to { visibility: hidden; }
  }
}

@layer base {
  html, body, #root { height: 100%; }
  body {
    @apply bg-white text-zinc-900 antialiased dark:bg-zinc-950 dark:text-zinc-100;
    font-feature-settings: "cv11", "ss01";
  }
  ::selection { @apply bg-brand-500/25; }
  * { scrollbar-width: thin; scrollbar-color: rgb(161 161 170 / 0.35) transparent; }
  button { cursor: pointer; }
  button:disabled { cursor: not-allowed; }
}

@utility text-gradient {
  background-image: linear-gradient(120deg, var(--color-brand-500), var(--color-accent-500));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

@utility shimmer-text {
  background-image: linear-gradient(90deg, currentColor 0%, currentColor 40%, rgb(161 161 170 / 0.5) 50%, currentColor 60%, currentColor 100%);
  background-size: 200% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: var(--animate-shimmer);
}

/* Markdown answers */
.markdown { @apply text-[15px] leading-7 text-zinc-800 dark:text-zinc-200; }
.markdown > * + * { @apply mt-3; }
.markdown p { @apply leading-7; }
.markdown strong { @apply font-semibold text-zinc-900 dark:text-white; }
.markdown ul { @apply list-disc space-y-1 pl-5 marker:text-zinc-400; }
.markdown ol { @apply list-decimal space-y-1 pl-5 marker:text-zinc-400; }
.markdown h1, .markdown h2, .markdown h3 { @apply mt-5 font-semibold text-zinc-900 dark:text-white; }
.markdown h1 { @apply text-xl; }
.markdown h2 { @apply text-lg; }
.markdown h3 { @apply text-base; }
.markdown a { @apply text-brand-600 underline underline-offset-2 dark:text-brand-400; }
.markdown code { @apply rounded-md bg-zinc-100 px-1.5 py-0.5 font-mono text-[13px] dark:bg-zinc-800; }
.markdown pre { @apply overflow-x-auto rounded-xl bg-zinc-100 p-4 dark:bg-zinc-900; }
.markdown pre code { @apply bg-transparent p-0; }
.markdown table { @apply w-full border-collapse text-sm; }
.markdown th, .markdown td { @apply border border-zinc-200 px-3 py-1.5 text-left dark:border-zinc-800; }
.markdown blockquote { @apply border-l-2 border-brand-500 pl-4 text-zinc-600 dark:text-zinc-400; }

/* Chart tokens: validated categorical palette, stepped separately for each mode */
:root {
  --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a; --series-4: #eda100;
  --series-5: #e87ba4; --series-6: #008300; --series-7: #6250d6; --series-8: #e34948;
  --chart-grid: #e7e7e4; --chart-axis: #52514e; --chart-surface: #ffffff;
}
.dark {
  --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --series-4: #c98500;
  --series-5: #d55181; --series-6: #008300; --series-7: #9085e9; --series-8: #e66767;
  --chart-grid: #2a2a28; --chart-axis: #c3c2b7; --chart-surface: #09090b;
}
```

### Button: `src/components/ui/Button.tsx`

```tsx
import { type ButtonHTMLAttributes, forwardRef } from "react";

import { cn } from "@/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "icon";

const variants: Record<Variant, string> = {
  primary:
    "bg-zinc-900 text-white shadow-sm hover:bg-zinc-800 dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-200",
  secondary:
    "border border-zinc-200 bg-white text-zinc-800 shadow-sm hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800",
  ghost: "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800/70 dark:hover:text-zinc-100",
  danger: "text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10",
};

const sizes: Record<Size, string> = {
  sm: "h-8 gap-1.5 rounded-lg px-2.5 text-[13px]",
  md: "h-10 gap-2 rounded-xl px-4 text-sm",
  icon: "h-8 w-8 rounded-lg",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "secondary", size = "md", type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex shrink-0 items-center justify-center font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 disabled:opacity-50",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";
```

### Dialog: `src/components/ui/Dialog.tsx`

```tsx
import { X } from "lucide-react";
import { type ReactNode, useEffect } from "react";

import { Button } from "./Button";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
}

export function Dialog({ open, onClose, title, description, children }: DialogProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-zinc-950/40 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div className="relative max-h-[92vh] w-full overflow-y-auto rounded-t-2xl border border-zinc-200 bg-white shadow-2xl animate-fade-in sm:max-w-lg sm:rounded-2xl dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-start justify-between gap-4 px-6 pt-5">
          <div>
            <h2 className="text-base font-semibold">{title}</h2>
            {description && <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{description}</p>}
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="px-6 pt-4 pb-6">{children}</div>
      </div>
    </div>
  );
}
```

### Model picker: `src/components/chat/ModelPicker.tsx`

```tsx
import { Check, ChevronDown, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/utils";
import { useApp } from "@/hooks/useApp";
import type { ModelInfo } from "@/types";

export function ModelPicker() {
  const config = useApp((s) => s.config);
  const model = useApp((s) => s.model);
  const setModel = useApp((s) => s.setModel);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  // Drop a stale selection if the server no longer offers it.
  useEffect(() => {
    if (config && model !== "auto" && !config.models.some((m) => m.id === model)) setModel("auto");
  }, [config, model, setModel]);

  if (!config) return null;
  const selected = config.models.find((m) => m.id === model);
  const groups = config.models.reduce<Record<string, ModelInfo[]>>((acc, m) => {
    (acc[m.provider_label] ??= []).push(m);
    return acc;
  }, {});

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex h-9 items-center gap-1.5 rounded-xl px-3 text-sm font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800/70"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {selected ? <span className="max-w-[180px] truncate">{selected.label}</span> : (
          <>
            <Sparkles className="h-4 w-4 text-brand-500" /> Auto
          </>
        )}
        <ChevronDown className="h-4 w-4 text-zinc-400" />
      </button>

      {open && (
        <div
          role="listbox"
          className="absolute top-11 left-0 z-40 max-h-[70vh] w-[min(340px,calc(100vw-2rem))] overflow-y-auto rounded-2xl border border-zinc-200 bg-white p-1.5 shadow-xl animate-fade-in dark:border-zinc-800 dark:bg-zinc-900"
        >
          <Option
            active={model === "auto"}
            onClick={() => (setModel("auto"), setOpen(false))}
            title="Auto"
            subtitle="Primary, then secondary fallback"
            badge="Recommended"
          />
          {Object.entries(groups).map(([provider, items]) => (
            <div key={provider} className="mt-1.5">
              <p className="px-2.5 pt-1.5 pb-1 text-[11px] font-medium tracking-wide text-zinc-400 uppercase">{provider}</p>
              {items.map((m) => (
                <Option
                  key={m.id}
                  active={model === m.id}
                  onClick={() => (setModel(m.id), setOpen(false))}
                  title={m.label}
                  subtitle={m.name}
                  badge={m.roles.includes("primary") ? "Primary" : m.roles[0]}
                />
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Option(props: { active: boolean; onClick: () => void; title: string; subtitle: string; badge?: string }) {
  return (
    <button
      role="option"
      aria-selected={props.active}
      onClick={props.onClick}
      className={cn(
        "flex w-full items-start gap-2.5 rounded-xl px-2.5 py-2 text-left hover:bg-zinc-100 dark:hover:bg-zinc-800",
        props.active && "bg-zinc-50 dark:bg-zinc-800/60",
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">{props.title}</span>
          {props.badge && (
            <span className="shrink-0 rounded-md bg-brand-50 px-1.5 py-0.5 text-[10px] font-medium text-brand-600 capitalize dark:bg-brand-500/15 dark:text-brand-400">
              {props.badge}
            </span>
          )}
        </div>
        <p className="mt-0.5 truncate text-xs text-zinc-500">{props.subtitle}</p>
      </div>
      {props.active && <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />}
    </button>
  );
}
```

### Step trace: `src/components/chat/AgentTrace.tsx`

```tsx
import { BarChart3, Check, ChevronDown, CircleSlash, Code2, Compass, Database, Loader2, MessageSquare, Play, ShieldCheck, Sparkles, TriangleAlert } from "lucide-react";
import { type ComponentType, useState } from "react";

import { cn, formatDuration } from "@/utils";
import type { AgentStep, AssistantStatus } from "@/types";

const KIND_ICONS: Record<string, ComponentType<{ className?: string }>> = {
  route: Compass,
  schema: Database,
  sql: Code2,
  guard: ShieldCheck,
  execute: Play,
  chart: BarChart3,
  insight: Sparkles,
  answer: MessageSquare,
};

function StatusIcon({ status }: { status: AgentStep["status"] }) {
  if (status === "running") return <Loader2 className="h-3.5 w-3.5 animate-spin text-brand-500" />;
  if (status === "error") return <TriangleAlert className="h-3.5 w-3.5 text-amber-500" />;
  if (status === "skipped") return <CircleSlash className="h-3.5 w-3.5 text-zinc-400" />;
  return <Check className="h-3.5 w-3.5 text-emerald-500" />;
}

export function AgentTrace({ steps, status }: { steps: AgentStep[]; status: AssistantStatus }) {
  const [open, setOpen] = useState<boolean | null>(null);
  if (!steps.length) {
    return status === "streaming" ? (
      <div className="flex items-center gap-2 text-sm text-zinc-500">
        <Loader2 className="h-4 w-4 animate-spin text-brand-500" />
        <span className="shimmer-text">Starting agents…</span>
      </div>
    ) : null;
  }

  const running = steps.find((s) => s.status === "running");
  const total = steps.reduce((sum, s) => sum + (s.duration_ms ?? 0), 0);
  const issues = steps.filter((s) => s.status === "error").length;
  // Live-expanded while streaming, collapsed afterwards, unless the user toggled it.
  const expanded = open ?? status === "streaming";

  return (
    <div className="rounded-xl border border-zinc-200/80 bg-zinc-50/60 dark:border-zinc-800 dark:bg-zinc-900/40">
      <button
        onClick={() => setOpen(!expanded)}
        className="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left text-[13px]"
        aria-expanded={expanded}
      >
        {running ? (
          <>
            <Loader2 className="h-4 w-4 shrink-0 animate-spin text-brand-500" />
            <span className="shimmer-text font-medium text-zinc-700 dark:text-zinc-300">{running.label}…</span>
          </>
        ) : (
          <>
            <Sparkles className="h-4 w-4 shrink-0 text-brand-500" />
            <span className="font-medium text-zinc-700 dark:text-zinc-300">
              {status === "stopped" ? "Stopped" : "Reasoned"} in {formatDuration(total)}
            </span>
            <span className="text-zinc-400">·</span>
            <span className="text-zinc-500">
              {steps.length} {steps.length === 1 ? "step" : "steps"}{issues ? `, ${issues} self-corrected` : ""}
            </span>
          </>
        )}
        <ChevronDown className={cn("ml-auto h-4 w-4 shrink-0 text-zinc-400 transition-transform", expanded && "rotate-180")} />
      </button>

      {expanded && (
        <ol className="relative space-y-0.5 border-t border-zinc-200/80 px-3.5 py-3 dark:border-zinc-800">
          {steps.map((step, i) => {
            const Icon = KIND_ICONS[step.kind] ?? Sparkles;
            return (
              <li key={step.id} className="relative flex gap-3 pb-2 animate-fade-in">
                {i < steps.length - 1 && (
                  <span className="absolute top-7 bottom-0 left-[13px] w-px bg-zinc-200 dark:bg-zinc-800" aria-hidden />
                )}
                <span className="relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900">
                  <Icon className="h-3.5 w-3.5 text-zinc-500 dark:text-zinc-400" />
                </span>
                <div className="min-w-0 flex-1 pt-1">
                  <div className="flex items-center gap-2 text-[13px]">
                    <StatusIcon status={step.status} />
                    <span className="font-medium text-zinc-800 dark:text-zinc-200">{step.label}</span>
                    {step.duration_ms !== undefined && step.status !== "running" && (
                      <span className="ml-auto shrink-0 font-mono text-[11px] text-zinc-400">
                        {formatDuration(step.duration_ms)}
                      </span>
                    )}
                  </div>
                  {step.detail && (
                    <p
                      className={cn(
                        "mt-0.5 text-xs leading-5 break-words",
                        step.status === "error" ? "text-amber-600 dark:text-amber-400" : "text-zinc-500",
                      )}
                    >
                      {step.detail}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
```

### Composer: `src/components/chat/Composer.tsx`

```tsx
import { ArrowUp, Lock, Square } from "lucide-react";
import { useEffect, useRef } from "react";

import { cn } from "@/utils";
import { useApp } from "@/hooks/useApp";

interface ComposerProps {
  busy: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}

export function Composer({ busy, onSend, onStop }: ComposerProps) {
  const draft = useApp((s) => s.draft);
  const setDraft = useApp((s) => s.setDraft);
  const connected = useApp((s) => !!s.connection.connection);
  const maxChars = useApp((s) => s.config?.limits.max_message_chars ?? 4000);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [draft]);

  useEffect(() => {
    if (connected) ref.current?.focus();
  }, [connected]);

  const tooLong = draft.length > maxChars;
  const canSend = connected && !busy && draft.trim().length > 0 && !tooLong;

  const submit = () => {
    if (!canSend) return;
    onSend(draft);
    setDraft("");
  };

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-4 sm:px-6">
      <div
        className={cn(
          "rounded-2xl border bg-white shadow-[0_2px_16px_-6px_rgb(0_0_0/0.12)] transition-colors focus-within:border-zinc-400 dark:bg-zinc-900 dark:focus-within:border-zinc-600",
          tooLong ? "border-red-400" : "border-zinc-200 dark:border-zinc-800",
        )}
      >
        <textarea
          ref={ref}
          rows={1}
          value={draft}
          disabled={!connected}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={connected ? "Ask anything about your data…" : "Connect a database to start asking questions"}
          className="block max-h-[220px] w-full resize-none bg-transparent px-4 pt-3.5 pb-1 text-[15px] leading-6 outline-none placeholder:text-zinc-400 disabled:cursor-not-allowed"
          aria-label="Message"
        />
        <div className="flex items-center gap-2 px-3 pb-2.5">
          <span className="flex items-center gap-1 text-[11px] text-zinc-400">
            <Lock className="h-3 w-3" /> Read-only
          </span>
          {draft.length > maxChars * 0.8 && (
            <span className={cn("text-[11px] tabular-nums", tooLong ? "text-red-500" : "text-zinc-400")}>
              {draft.length}/{maxChars}
            </span>
          )}
          {busy ? (
            <button
              onClick={onStop}
              className="ml-auto flex h-8 w-8 items-center justify-center rounded-full bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-white dark:text-zinc-900"
              aria-label="Stop generating"
            >
              <Square className="h-3 w-3 fill-current" />
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={!canSend}
              className="ml-auto flex h-8 w-8 items-center justify-center rounded-full bg-zinc-900 text-white transition hover:bg-zinc-700 disabled:bg-zinc-200 disabled:text-zinc-400 dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-200 dark:disabled:bg-zinc-800 dark:disabled:text-zinc-600"
              aria-label="Send message"
            >
              <ArrowUp className="h-4 w-4" strokeWidth={2.5} />
            </button>
          )}
        </div>
      </div>
      <p className="mt-2 text-center text-[11px] text-zinc-400">
        DataPilot can make mistakes. Verify important numbers against the SQL shown.
      </p>
    </div>
  );
}
```

### Chat page layout: `src/components/chat/ChatView.tsx`

Includes the header and "follow the stream unless the user scrolled up" behaviour.

```tsx
import { ArrowDown, Menu, SquarePen } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { useChat } from "@/hooks/useChat";
import { useConnection } from "@/hooks/useConnection";
import { useApp } from "@/hooks/useApp";

import { Composer } from "./Composer";
import { EmptyState } from "./EmptyState";
import { AssistantMessage, UserMessage } from "./Messages";
import { ModelPicker } from "./ModelPicker";

export function ChatView() {
  const messages = useApp((s) => s.messages);
  const connection = useApp((s) => s.connection.connection);
  const setSidebarOpen = useApp((s) => s.setSidebarOpen);
  const newChat = useApp((s) => s.newChat);
  const { send, stop, busy } = useChat();
  const { connect, pending } = useConnection();

  const scrollRef = useRef<HTMLDivElement>(null);
  const [pinned, setPinned] = useState(true);

  // Follow the stream only while the user is at the bottom.
  useEffect(() => {
    const el = scrollRef.current;
    if (el && pinned) el.scrollTop = el.scrollHeight;
  }, [messages, pinned]);

  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (el) setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
  }, []);

  const sendAndPin = (text: string) => {
    setPinned(true);
    void send(text);
  };

  const retry = (index: number) => {
    const prev = messages[index - 1];
    if (prev?.role === "user") sendAndPin(prev.content);
  };

  return (
    <main className="flex min-w-0 flex-1 flex-col">
      <header className="flex h-14 shrink-0 items-center gap-1 border-b border-zinc-200/70 px-3 sm:px-4 dark:border-zinc-800/70">
        <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setSidebarOpen(true)} aria-label="Open sidebar">
          <Menu className="h-4 w-4" />
        </Button>
        <ModelPicker />
        <div className="ml-auto flex items-center gap-2">
          {connection && (
            <span className="hidden max-w-[240px] truncate rounded-full border border-zinc-200 px-2.5 py-1 text-xs text-zinc-500 sm:block dark:border-zinc-800">
              {connection.name}
            </span>
          )}
          {messages.length > 0 && (
            <Button variant="ghost" size="icon" onClick={newChat} aria-label="New chat" title="New chat">
              <SquarePen className="h-4 w-4" />
            </Button>
          )}
        </div>
      </header>

      <div ref={scrollRef} onScroll={onScroll} className="relative flex min-h-0 flex-1 flex-col overflow-y-auto">
        {messages.length === 0 ? (
          <EmptyState onPick={sendAndPin} onTryDemo={() => void connect({ type: "sqlite_demo" })} connecting={pending} />
        ) : (
          <div className="mx-auto w-full max-w-3xl space-y-8 px-4 py-8 sm:px-6">
            {messages.map((m, i) =>
              m.role === "user" ? (
                <UserMessage key={m.id} message={m} />
              ) : (
                <AssistantMessage key={m.id} message={m} onRetry={!busy && i === messages.length - 1 ? () => retry(i) : undefined} />
              ),
            )}
          </div>
        )}
      </div>

      <div className="relative">
        {!pinned && messages.length > 0 && (
          <button
            onClick={() => setPinned(true)}
            className="absolute -top-12 left-1/2 flex h-8 w-8 -translate-x-1/2 items-center justify-center rounded-full border border-zinc-200 bg-white shadow-md dark:border-zinc-700 dark:bg-zinc-900"
            aria-label="Scroll to bottom"
          >
            <ArrowDown className="h-4 w-4" />
          </button>
        )}
        <Composer busy={busy} onSend={sendAndPin} onStop={stop} />
      </div>
    </main>
  );
}
```

### Messages: `src/components/chat/Messages.tsx`

Replace `ChartView`, `ResultTable` and `SqlBlock` with the Sources block.

```tsx
import { AlertCircle, Cpu, RotateCcw } from "lucide-react";
import { lazy, Suspense } from "react";

import { Logo } from "@/components/ui/Logo";
import { useApp } from "@/hooks/useApp";
import type { AssistantMessage as AssistantMsg, UserMessage as UserMsg } from "@/types";

import { AgentTrace } from "./AgentTrace";
import { Markdown } from "./Markdown";
import { ResultTable } from "./ResultTable";
import { SqlBlock } from "./SqlBlock";

// Recharts is the heaviest dependency; load it only when a chart is shown.
const ChartView = lazy(() => import("./ChartView").then((m) => ({ default: m.ChartView })));

export function UserMessage({ message }: { message: UserMsg }) {
  return (
    <div className="flex justify-end animate-fade-in">
      <div className="max-w-[85%] rounded-2xl rounded-br-md bg-zinc-100 px-4 py-2.5 text-[15px] leading-7 whitespace-pre-wrap text-zinc-900 dark:bg-zinc-800/80 dark:text-zinc-100">
        {message.content}
      </div>
    </div>
  );
}

export function AssistantMessage({ message, onRetry }: { message: AssistantMsg; onRetry?: () => void }) {
  const models = useApp((s) => s.config?.models);
  const streaming = message.status === "streaming";
  const modelLabels = message.models
    .map((id) => models?.find((m) => m.id === id)?.label ?? id.split(":").pop())
    .filter(Boolean);

  return (
    <div className="flex gap-3 animate-fade-in sm:gap-4">
      <Logo className="mt-0.5 h-7 w-7 shrink-0" />
      <div className="min-w-0 flex-1 space-y-4">
        <AgentTrace steps={message.steps} status={message.status} />

        {message.content && (
          <div>
            <Markdown text={message.content} />
            {streaming && message.steps.some((s) => s.status === "running" && (s.kind === "insight" || s.kind === "answer")) && (
              <span className="ml-0.5 inline-block h-4 w-[3px] translate-y-0.5 animate-blink rounded-sm bg-brand-500" />
            )}
          </div>
        )}

        {message.chart && message.result && (
          <Suspense fallback={<div className="h-[22rem] animate-pulse rounded-xl border border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/40" />}>
            <ChartView spec={message.chart} result={message.result} />
          </Suspense>
        )}
        {message.result && <ResultTable result={message.result} />}
        {message.sql && <SqlBlock sql={message.sql.sql} explanation={message.sql.explanation} />}

        {message.error && (
          <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <p className="flex-1 break-words">{message.error.message}</p>
            {onRetry && (
              <button onClick={onRetry} className="flex shrink-0 items-center gap-1 text-xs font-medium hover:underline">
                <RotateCcw className="h-3.5 w-3.5" /> Retry
              </button>
            )}
          </div>
        )}

        {message.status === "stopped" && <p className="text-xs text-zinc-500 italic">Generation stopped.</p>}

        {!streaming && modelLabels.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-zinc-400">
            <Cpu className="h-3 w-3" />
            {modelLabels.map((l) => (
              <span key={l} className="rounded-md bg-zinc-100 px-1.5 py-0.5 font-mono dark:bg-zinc-800/80">
                {l}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

### Markdown: `src/components/chat/Markdown.tsx`

```tsx
import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export const Markdown = memo(function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{ a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noreferrer noopener" /> }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
});
```

### Empty state: `src/components/chat/EmptyState.tsx`

```tsx
import { ArrowRight, BarChart3, Database, Globe2, LineChart, PlugZap, ShieldCheck, Sparkles, TrendingUp } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";
import { useApp } from "@/hooks/useApp";

const DEMO_SUGGESTIONS = [
  { icon: TrendingUp, text: "Which 10 countries have the highest GDP per capita?" },
  { icon: BarChart3, text: "Plot total GDP by continent as a bar chart" },
  { icon: Globe2, text: "Compare literacy rate and AI startups for Asian countries" },
  { icon: LineChart, text: "Which countries earn the most from tourism relative to GDP?" },
];

const GENERIC_SUGGESTIONS = [
  { icon: Database, text: "What data is available in this database?" },
  { icon: TrendingUp, text: "Show the 10 largest records by value in the main table" },
  { icon: BarChart3, text: "Chart the number of records per category" },
  { icon: Sparkles, text: "Summarise the key trends in this data" },
];

export function EmptyState({ onPick, onTryDemo, connecting }: { onPick: (t: string) => void; onTryDemo: () => void; connecting: boolean }) {
  const connection = useApp((s) => s.connection.connection);
  const setConnectOpen = useApp((s) => s.setConnectOpen);
  const suggestions = connection?.type === "sqlite_demo" ? DEMO_SUGGESTIONS : GENERIC_SUGGESTIONS;

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-4 py-10 sm:px-6">
      <div className="relative mb-6">
        <div className="absolute inset-0 -z-10 scale-150 rounded-full bg-gradient-to-br from-brand-500/25 to-accent-500/25 blur-2xl" />
        <Logo className="h-12 w-12" />
      </div>
      <h1 className="text-center text-2xl font-semibold tracking-tight sm:text-3xl">
        {connection ? (
          <>
            What would you like to <span className="text-gradient">know</span>?
          </>
        ) : (
          <>
            Talk to your data in <span className="text-gradient">plain English</span>
          </>
        )}
      </h1>
      <p className="mt-3 max-w-lg text-center text-sm leading-6 text-zinc-500 dark:text-zinc-400">
        {connection
          ? `Connected to ${connection.name}. A team of agents will plan, write, verify and run read-only SQL, then explain the results.`
          : "Connect PostgreSQL, MySQL or try the demo database. Agents translate your questions into safe, read-only SQL, then explain and chart the results."}
      </p>

      {connection ? (
        <div className="mt-8 grid w-full gap-2.5 sm:grid-cols-2">
          {suggestions.map(({ icon: Icon, text }) => (
            <button
              key={text}
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
        <div className="mt-8 flex flex-col gap-2.5 sm:flex-row">
          <Button variant="primary" onClick={onTryDemo} disabled={connecting}>
            <Sparkles className="h-4 w-4" /> {connecting ? "Loading demo…" : "Try the demo database"}
          </Button>
          <Button onClick={() => setConnectOpen(true)}>
            <PlugZap className="h-4 w-4" /> Connect your database
          </Button>
        </div>
      )}

      <div className="mt-10 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-zinc-400">
        <span className="flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5" /> Read-only, enforced 3 ways</span>
        <span className="flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5" /> Self-correcting SQL agents</span>
        <span className="flex items-center gap-1.5"><BarChart3 className="h-3.5 w-3.5" /> Charts on request</span>
      </div>
    </div>
  );
}
```

### Sidebar: `src/components/sidebar/Sidebar.tsx`

Includes the user row, theme toggle and mobile drawer.

```tsx
import { Database, LogOut, Moon, PlugZap, RefreshCw, SquarePen, Sun, Unplug, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";
import { useConnection } from "@/hooks/useConnection";
import { cn, displayName, initials } from "@/utils";
import { useApp } from "@/hooks/useApp";
import { useAuth } from "@/hooks/useAuth";

import { SchemaExplorer } from "./SchemaExplorer";

const DIALECT_LABEL: Record<string, string> = { sqlite: "SQLite", postgres: "PostgreSQL", mysql: "MySQL" };

function useTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem("dp-theme", dark ? "dark" : "light");
    } catch {
      /* storage unavailable */
    }
  }, [dark]);
  return { dark, toggle: () => setDark((d) => !d) };
}

function UserCard() {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  if (!user) return null;
  const isEmail = user.email.includes("@");
  return (
    <div className="mx-3 mt-3 flex items-center gap-2.5 rounded-xl px-1.5 py-1">
      <span
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-accent-500 text-xs font-semibold text-white"
        aria-hidden
      >
        {initials(user.email)}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium" title={user.email}>{displayName(user.email)}</p>
        <p className="truncate text-xs text-zinc-500">{isEmail ? user.email : "Demo account"}</p>
      </div>
      <Button variant="ghost" size="icon" onClick={logout} aria-label="Log out" title="Log out">
        <LogOut className="h-4 w-4" />
      </Button>
    </div>
  );
}

export function Sidebar() {
  const open = useApp((s) => s.sidebarOpen);
  const setOpen = useApp((s) => s.setSidebarOpen);
  const connection = useApp((s) => s.connection.connection);
  const newChat = useApp((s) => s.newChat);
  const setConnectOpen = useApp((s) => s.setConnectOpen);
  const { disconnect, refresh, pending } = useConnection();
  const { dark, toggle } = useTheme();

  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-zinc-950/40 lg:hidden" onClick={() => setOpen(false)} />}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[280px] flex-col border-r border-zinc-200 bg-zinc-50 transition-transform duration-200 lg:static lg:translate-x-0 dark:border-zinc-800/80 dark:bg-zinc-900/50",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center gap-2.5 px-4 pt-4 pb-3">
          <Logo />
          <span className="text-[15px] font-semibold tracking-tight">DataPilot</span>
          <span className="rounded-md bg-zinc-200/70 px-1.5 py-0.5 text-[10px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">AI</span>
          <Button variant="ghost" size="icon" className="ml-auto lg:hidden" onClick={() => setOpen(false)} aria-label="Close sidebar">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="px-3">
          <Button variant="secondary" className="w-full justify-start" onClick={() => (newChat(), setOpen(false))}>
            <SquarePen className="h-4 w-4" /> New chat
          </Button>
        </div>

        <UserCard />

        <div className="mx-3 mt-4 mb-3 rounded-xl border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900">
          {connection ? (
            <>
              <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
                </span>
                <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Connected · read-only</span>
              </div>
              <p className="mt-2 truncate text-sm font-medium" title={connection.name}>{connection.name}</p>
              <p className="text-xs text-zinc-500">{DIALECT_LABEL[connection.dialect] ?? connection.dialect}</p>
              <div className="mt-3 flex gap-1">
                <Button variant="ghost" size="sm" onClick={() => setConnectOpen(true)}>
                  <PlugZap className="h-3.5 w-3.5" /> Switch
                </Button>
                <Button variant="ghost" size="sm" onClick={refresh} disabled={pending} aria-label="Refresh schema">
                  <RefreshCw className={cn("h-3.5 w-3.5", pending && "animate-spin")} />
                </Button>
                <Button variant="danger" size="sm" className="ml-auto" onClick={disconnect} aria-label="Disconnect">
                  <Unplug className="h-3.5 w-3.5" />
                </Button>
              </div>
            </>
          ) : (
            <>
              <div className="flex items-center gap-2 text-sm font-medium">
                <Database className="h-4 w-4 text-zinc-400" /> No database
              </div>
              <p className="mt-1 text-xs leading-5 text-zinc-500">Connect a database or load the demo to start.</p>
              <Button variant="primary" size="sm" className="mt-3 w-full" onClick={() => setConnectOpen(true)}>
                <PlugZap className="h-3.5 w-3.5" /> Connect
              </Button>
            </>
          )}
        </div>

        <SchemaExplorer />

        <div className="mt-auto flex items-center justify-between border-t border-zinc-200 px-4 py-3 text-xs text-zinc-500 dark:border-zinc-800">
          <span>Chats stay in this tab only</span>
          <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle theme">
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </div>
      </aside>
    </>
  );
}
```

### Login and signup page: `src/components/auth/AuthPage.tsx`

The "Demo account" box is optional. Keep it only if RAGDocs has a real demo account.

```tsx
import { Eye, EyeOff, KeyRound, Loader2 } from "lucide-react";
import { type FormEvent, useState } from "react";

import { ApiError } from "@/api";
import { Button } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";
import { DEMO_ACCOUNT, useAuth } from "@/hooks/useAuth";
import { cn } from "@/utils";

type Mode = "login" | "signup";

const inputClass =
  "h-10 w-full rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none transition-colors placeholder:text-zinc-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 dark:border-zinc-800 dark:bg-zinc-900";

export function AuthPage() {
  const login = useAuth((s) => s.login);
  const signup = useAuth((s) => s.signup);
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const switchMode = (next: Mode) => {
    setMode(next);
    setError("");
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setPending(true);
    setError("");
    try {
      await (mode === "login" ? login : signup)(email, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setPending(false);
    }
  };

  const fillDemo = () => {
    switchMode("login");
    setEmail(DEMO_ACCOUNT.email);
    setPassword(DEMO_ACCOUNT.password);
  };

  return (
    <div className="flex min-h-full items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm animate-fade-in">
        <div className="flex flex-col items-center text-center">
          <Logo className="h-10 w-10" />
          <h1 className="mt-4 text-xl font-semibold tracking-tight">
            {mode === "login" ? "Log in to DataPilot" : "Create your account"}
          </h1>
          <p className="mt-1 text-sm text-zinc-500">Ask your database questions in plain English.</p>
        </div>

        <div className="mt-6 grid grid-cols-2 rounded-xl bg-zinc-100 p-1 text-sm dark:bg-zinc-900">
          {(["login", "signup"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => switchMode(m)}
              className={cn(
                "h-8 rounded-lg font-medium transition-colors",
                mode === m
                  ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-800 dark:text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200",
              )}
            >
              {m === "login" ? "Log in" : "Sign up"}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="mt-5 space-y-3">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">Email</span>
            <input
              className={inputClass}
              type={mode === "signup" ? "email" : "text"}
              autoComplete={mode === "login" ? "username" : "email"}
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">Password</span>
            <div className="relative">
              <input
                className={cn(inputClass, "pr-10")}
                type={showPassword ? "text" : "password"}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                placeholder={mode === "signup" ? "At least 8 characters, a letter and a number" : "Your password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </label>

          {error && (
            <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600 dark:bg-red-500/10 dark:text-red-400">
              {error}
            </p>
          )}

          <Button type="submit" variant="primary" className="w-full" disabled={pending}>
            {pending && <Loader2 className="h-4 w-4 animate-spin" />}
            {mode === "login" ? "Log in" : "Create account"}
          </Button>
        </form>

        <div className="mt-6 rounded-xl border border-dashed border-zinc-300 p-4 dark:border-zinc-700">
          <div className="flex items-center gap-2 text-sm font-medium">
            <KeyRound className="h-4 w-4 text-brand-500" /> Demo account
          </div>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-zinc-500">Email</dt>
            <dd className="font-mono">{DEMO_ACCOUNT.email}</dd>
            <dt className="text-zinc-500">Password</dt>
            <dd className="font-mono">{DEMO_ACCOUNT.password}</dd>
          </dl>
          <Button variant="secondary" size="sm" className="mt-3 w-full" onClick={fillDemo}>
            Use demo account
          </Button>
        </div>
      </div>
    </div>
  );
}
```

### App shell: `src/App.tsx`

```tsx
import { AlertTriangle, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { AuthPage } from "@/components/auth/AuthPage";
import { ChatView } from "@/components/chat/ChatView";
import { ConnectionDialog } from "@/components/connection/ConnectionDialog";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { Button } from "@/components/ui/Button";
import { api, ApiError } from "@/api";
import { useApp } from "@/hooks/useApp";
import { useAuth } from "@/hooks/useAuth";

export default function App() {
  const user = useAuth((s) => s.user);
  if (!user) return <AuthPage />;
  // Keyed by user, so logging in as someone else starts from a clean state.
  return <Workspace key={user.id} />;
}

function Workspace() {
  const setConfig = useApp((s) => s.setConfig);
  const setConnection = useApp((s) => s.setConnection);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");

  const boot = async () => {
    setStatus("loading");
    try {
      const [config, connection] = await Promise.all([api.config(), api.currentConnection()]);
      setConfig(config);
      setConnection(connection);
      setStatus("ready");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load.");
      setStatus("error");
    }
  };

  useEffect(() => {
    void boot();
  }, []); // run once on mount

  if (status !== "ready") {
    return (
      <div className="flex h-full items-center justify-center p-6">
        {status === "loading" ? (
          <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
        ) : (
          <div className="max-w-sm text-center">
            <AlertTriangle className="mx-auto h-8 w-8 text-amber-500" />
            <p className="mt-3 font-medium">DataPilot is unavailable</p>
            <p className="mt-1 text-sm text-zinc-500">{error}</p>
            <Button className="mt-5" onClick={boot}>
              Try again
            </Button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden">
      <Sidebar />
      <ChatView />
      <ConnectionDialog />
    </div>
  );
}
```
