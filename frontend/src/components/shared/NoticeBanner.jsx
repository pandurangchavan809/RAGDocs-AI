function NoticeBanner({ notice }) {
  if (!notice?.message) {
    return null;
  }

  return (
    <div
      className={`fixed right-5 top-5 z-50 rounded-2xl border px-4 py-3 text-sm shadow-glow ${
        notice.type === "success"
          ? "border-emerald-400/30 bg-emerald-500/15 text-emerald-100"
          : "border-sky-400/30 bg-sky-500/15 text-sky-100"
      }`}
    >
      {notice.message}
    </div>
  );
}

export default NoticeBanner;
