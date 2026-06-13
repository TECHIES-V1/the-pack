import type { Config } from "tailwindcss";

// Design tokens (Doc 05 §05 — design direction seed). The PACK palette: ink navy + the
// orange accent from the doc covers. Wolf-state colors drive the WolfNode/EdgeFlow matrix.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#1f2a3c", // doc-cover navy
          soft: "#2b3a52",
        },
        bone: "#f7f3ec", // doc-cover paper
        accent: {
          DEFAULT: "#e6a23c", // doc-cover orange
          soft: "#f0c987",
        },
        wolf: {
          idle: "#9ca3af",
          hunting: "#e6a23c",
          talking: "#5b9bd5",
          holding: "#c084fc",
          stray: "#eb3424",
          done: "#3fb27f",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      keyframes: {
        shimmer: {
          "0%, 100%": { opacity: "0.55" },
          "50%": { opacity: "1" },
        },
        pulse_edge: {
          "0%": { strokeDashoffset: "16" },
          "100%": { strokeDashoffset: "0" },
        },
      },
      animation: {
        // Sentinel/Alpha thinking shimmer.
        shimmer: "shimmer 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
