module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "app-bg": "#070A08",
        "surface-sidebar": "#0C110E",
        "surface-card": "#121915",
        "surface-card-2": "#161F1A",
        "border-subtle": "#1F2922",
        "border-bright": "#2A3C30",
        primary: { DEFAULT: "#22C55E", hover: "#16A34A" },
        accent: {
          yellow: "#FACC15",
          orange: "#F97316",
          red: "#EF4444",
        },
        muted: "#8BA094",
        "text-main": "#F8FAFC",
      },
      fontFamily: {
        head: ['"Outfit"', "system-ui", "sans-serif"],
        body: ['"Manrope"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "monospace"],
      },
      boxShadow: {
        "ring-primary": "0 0 0 1px #22C55E",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
