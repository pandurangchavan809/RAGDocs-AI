/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef2ff",
          100: "#e0e7ff",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
        },
        accent: {
          500: "#06b6d4",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "none" },
        },
        shimmer: {
          from: { backgroundPosition: "-200% 0" },
          to: { backgroundPosition: "200% 0" },
        },
        blink: {
          to: { visibility: "hidden" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.25s ease-out both",
        shimmer: "shimmer 1.6s linear infinite",
        blink: "blink 1s steps(2, start) infinite",
      },
    },
  },
  plugins: [],
};
