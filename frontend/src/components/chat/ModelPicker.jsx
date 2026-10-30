import { Check, ChevronDown, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "../../utils/cn";

function getAutoSubtitle(config) {
  if (config.auto_models.length > 1) {
    return "Primary, then secondary fallback";
  }
  const only = config.models.find((item) => item.id === config.auto_models[0]);
  return only ? `Uses ${only.label}` : "Default model";
}

function ModelPicker({ config, model, onChange }) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const onMouseDown = (event) => {
      if (!containerRef.current?.contains(event.target)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event) => event.key === "Escape" && setOpen(false);

    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  if (!config?.models.length) {
    return null;
  }

  // With one usable model there is nothing to choose, so show it as a label.
  if (config.models.length === 1) {
    return (
      <span className="flex h-9 items-center gap-1.5 px-3 text-sm font-medium">
        <Sparkles className="h-4 w-4 text-brand-500" />
        <span className="max-w-[180px] truncate">{config.models[0].label}</span>
      </span>
    );
  }

  const selected = config.models.find((item) => item.id === model);
  const groups = config.models.reduce((result, item) => {
    (result[item.provider_label] ??= []).push(item);
    return result;
  }, {});

  const choose = (nextModel) => {
    onChange(nextModel);
    setOpen(false);
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex h-9 items-center gap-1.5 rounded-xl px-3 text-sm font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800/70"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {selected ? (
          <span className="max-w-[180px] truncate">{selected.label}</span>
        ) : (
          <>
            <Sparkles className="h-4 w-4 text-brand-500" /> Auto
          </>
        )}
        <ChevronDown className="h-4 w-4 text-zinc-400" />
      </button>

      {open && (
        <div
          role="listbox"
          className="absolute left-0 top-11 z-40 max-h-[70vh] w-[min(340px,calc(100vw-2rem))] animate-fade-in overflow-y-auto rounded-2xl border border-zinc-200 bg-white p-1.5 shadow-xl dark:border-zinc-800 dark:bg-zinc-900"
        >
          <Option
            active={!selected}
            onClick={() => choose("auto")}
            title="Auto"
            subtitle={getAutoSubtitle(config)}
            badge="Recommended"
          />
          {Object.entries(groups).map(([provider, items]) => (
            <div key={provider} className="mt-1.5">
              <p className="px-2.5 pb-1 pt-1.5 text-[11px] font-medium uppercase tracking-wide text-zinc-400">
                {provider}
              </p>
              {items.map((item) => (
                <Option
                  key={item.id}
                  active={model === item.id}
                  onClick={() => choose(item.id)}
                  title={item.label}
                  subtitle={item.name}
                  badge={item.roles[0]}
                />
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Option({ active, onClick, title, subtitle, badge }) {
  return (
    <button
      type="button"
      role="option"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "flex w-full items-start gap-2.5 rounded-xl px-2.5 py-2 text-left hover:bg-zinc-100 dark:hover:bg-zinc-800",
        active && "bg-zinc-50 dark:bg-zinc-800/60"
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">{title}</span>
          {badge && (
            <span className="shrink-0 rounded-md bg-brand-50 px-1.5 py-0.5 text-[10px] font-medium capitalize text-brand-600 dark:bg-brand-500/15 dark:text-brand-400">
              {badge}
            </span>
          )}
        </div>
        <p className="mt-0.5 truncate text-xs text-zinc-500">{subtitle}</p>
      </div>
      {active && <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />}
    </button>
  );
}

export default ModelPicker;
