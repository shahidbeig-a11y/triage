import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#08081a",
        card: "#0c0c1e",
        border: "#16163a",
        selected: "#16163a",
        primary: "#E0E0EE",
        secondary: "#8888a8",
        muted: "#55557a",
      },
    },
  },
  plugins: [],
};
export default config;
