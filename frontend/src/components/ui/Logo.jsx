import { useId } from "react";

function Logo({ className = "h-8 w-8" }) {
  const gradientId = useId().replace(/:/g, "");

  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6366f1" />
          <stop offset="1" stopColor="#06b6d4" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill={`url(#${gradientId})`} />
      <path d="M10 7h8l4.5 4.5V25H10z" fill="#fff" />
      <path d="M18 7v4.5h4.5z" fill="#c7d2fe" />
      <path
        d="M13 15.5h6.5M13 19h6.5"
        fill="none"
        stroke="#6366f1"
        strokeLinecap="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

export default Logo;
