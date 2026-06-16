import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#080b12",
        panel: "#101622",
        panelSoft: "#151d2b",
        line: "#243044",
        brand: "#67e8f9",
        signal: "#8b5cf6"
      },
      boxShadow: {
        glow: "0 0 40px rgba(103, 232, 249, 0.12)"
      }
    }
  },
  plugins: []
};

export default config;
