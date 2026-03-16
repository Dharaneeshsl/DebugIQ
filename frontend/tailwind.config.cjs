/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}"
  ],
  theme: {
    extend: {
      colors: {
        base: "#0f1117",
        panel: "#151a23",
        card: "#1b2230",
        accent: "#22c55e",
      },
    },
  },
  plugins: [],
};