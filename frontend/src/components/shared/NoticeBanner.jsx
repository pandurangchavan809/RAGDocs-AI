import { CheckCircle2 } from "lucide-react";

function NoticeBanner({ notice }) {
  if (!notice?.message) {
    return null;
  }

  return (
    <div
      role="status"
      className="fixed right-4 top-4 z-[60] flex animate-fade-in items-center gap-2 rounded-xl border border-zinc-200 bg-white px-3.5 py-2.5 text-sm shadow-xl dark:border-zinc-800 dark:bg-zinc-900"
    >
      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
      {notice.message}
    </div>
  );
}

export default NoticeBanner;
