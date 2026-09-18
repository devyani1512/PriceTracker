/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#37352f",
          secondary: "#787774",
          faint: "#9b9a97",
        },
        line: "#e9e9e7",
        hover: "#f7f7f5",
        panel: "#fbfbfa",
        code: "#2f3437",
        success: {
          bg: "#edf3ec",
          text: "#346538",
        },
        warning: {
          bg: "#fbf3db",
          text: "#8a6116",
        },
        danger: {
          bg: "#fdebec",
          text: "#9f2f2d",
        },
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
      },
      borderRadius: {
        sm: "3px",
        DEFAULT: "4px",
        md: "5px",
        lg: "6px",
      },
      maxWidth: {
        content: "1000px",
      },
    },
  },
  plugins: [],
};
