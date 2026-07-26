import type { Config } from "tailwindcss";

/**
 * Tailwind maps utilities onto the CSS custom properties defined in
 * globals.css. Colours are declared as `var(--token)` rather than hex values so
 * that a single class such as `bg-surface-panel` resolves correctly in both
 * themes, and no component carries `dark:` variants for colour.
 */
const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          base: "var(--surface-base)",
          panel: "var(--surface-panel)",
          raised: "var(--surface-raised)",
          sunken: "var(--surface-sunken)",
          hover: "var(--surface-hover)",
          active: "var(--surface-active)",
          overlay: "var(--surface-overlay)",
        },
        content: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          tertiary: "var(--text-tertiary)",
          "on-accent": "var(--text-on-accent)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          hover: "var(--accent-hover)",
          subtle: "var(--accent-subtle)",
        },
        bubble: {
          "in-bg": "var(--bubble-incoming-bg)",
          "in-text": "var(--bubble-incoming-text)",
          "out-bg": "var(--bubble-outgoing-bg)",
          "out-text": "var(--bubble-outgoing-text)",
        },
        edge: {
          subtle: "var(--border-subtle)",
          strong: "var(--border-strong)",
        },
        signal: {
          green: "var(--signal-green)",
          red: "var(--signal-red)",
          yellow: "var(--signal-yellow)",
          link: "var(--signal-link)",
        },
        /* The twelve conversation colours Signal assigns to avatars. Named, not
           numbered, because the backend stores the name on the user row. */
        avatar: {
          ultramarine: "#2c6bed",
          crimson: "#cf163e",
          vermilion: "#c73f0a",
          burlap: "#6f6a58",
          forest: "#3b7845",
          wintergreen: "#1d8663",
          teal: "#077d92",
          blue: "#336ba3",
          indigo: "#6058ca",
          violet: "#9932c8",
          plum: "#aa377a",
          taupe: "#8f616a",
          steel: "#71717f",
        },
      },
      spacing: {
        rail: "var(--nav-rail-width)",
        header: "var(--header-height)",
        list: "var(--list-width)",
      },
      borderRadius: {
        bubble: "var(--bubble-radius)",
        "bubble-grouped": "var(--bubble-radius-grouped)",
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "system-ui",
          "Segoe UI",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: ["SF Mono", "SFMono-Regular", "ui-monospace", "Menlo", "Consolas", "monospace"],
      },
      transitionTimingFunction: {
        "out-expo": "var(--ease-out-expo)",
      },
      zIndex: {
        // Mirrors Signal's stacking order, so a popover can never sit under a
        // modal by accident.
        popover: "100",
        "context-menu": "125",
        tooltip: "150",
        toast: "200",
        modal: "102",
      },
      keyframes: {
        "typing-bounce": {
          "0%, 60%, 100%": { transform: "translateY(0)", opacity: "0.4" },
          "30%": { transform: "translateY(-4px)", opacity: "1" },
        },
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "typing-bounce": "typing-bounce 1.4s infinite ease-in-out",
        "fade-in": "fade-in 150ms ease-out",
        "slide-up": "slide-up 180ms var(--ease-out-expo)",
      },
    },
  },
  plugins: [],
};

export default config;
