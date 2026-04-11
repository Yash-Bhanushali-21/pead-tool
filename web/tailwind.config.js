/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["DM Sans", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      colors: {
        surface: {
          DEFAULT: "#0f1419",
          raised: "#161c24",
          border: "#243040",
        },
        accent: { DEFAULT: "#38bdf8", muted: "#0c4a6e" },
      },
    },
  },
  plugins: [],
};
