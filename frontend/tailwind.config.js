/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        base: "#0a0f1c",
        panel: "#121a2b",
        line: "#25324a",
        soft: "#8ea0be",
        accent: "#86efac",
        accentDark: "#0f1e17",
      },
      fontFamily: {
        sans: ["Space Grotesk", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        glow: "0 18px 50px rgba(134, 239, 172, 0.08)",
      },
    },
  },
  plugins: [],
};
