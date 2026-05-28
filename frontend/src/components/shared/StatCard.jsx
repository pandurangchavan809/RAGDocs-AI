function StatCard({ title, value }) {
  return (
    <div className="rounded-3xl border border-line bg-white/5 p-4">
      <p className="text-xs uppercase tracking-[0.25em] text-soft">{title}</p>
      <p className="mt-3 text-lg font-semibold">{value}</p>
    </div>
  );
}

export default StatCard;
