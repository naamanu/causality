/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        // monospace-meets-editorial: data in mono, headlines in a serif display
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        serif: ["'Newsreader'", "Georgia", "Cambria", "serif"],
      },
      colors: {
        ink: {
          950: "#0a0b0d",
          900: "#0e1013",
          850: "#14171c",
          800: "#1b1f26",
          700: "#272c35",
          600: "#3a4150",
        },
        // status palette — reused by spans, logs, hypotheses
        ok: "#34d399",
        degraded: "#fbbf24",
        error: "#fb7185",
        accent: "#e2c08d", // warm editorial accent
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.35s cubic-bezier(0.22, 1, 0.36, 1) both",
      },
    },
  },
  plugins: [],
};
