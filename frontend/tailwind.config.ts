import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./features/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        tb: {
          primary: "var(--tb-primary)",
          "primary-soft": "var(--tb-primary-soft)",
          secondary: "var(--tb-secondary)",
          accent: "var(--tb-accent)",
          "accent-soft": "var(--tb-accent-soft)",
          bg: "var(--tb-bg)",
          elevated: "var(--tb-bg-elevated)",
          surface: "var(--tb-surface)",
          border: "var(--tb-border)",
          muted: "var(--tb-text-muted)",
          danger: "var(--tb-danger)",
          success: "var(--tb-success)",
        },
      },
      fontFamily: {
        display: ["var(--font-display)"],
        body: ["var(--font-body)"],
      },
      boxShadow: {
        soft: "0 18px 40px rgba(11, 61, 46, 0.08)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.55s ease-out both",
        "pulse-soft": "pulse-soft 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
