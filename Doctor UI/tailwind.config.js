/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#d4e6f1',
          100: '#a1c6e7',
          200: '#78a3db',
          300: '#4b8cce',
          400: '#0f6fbb',
          500: '#4b8c9c',
          600: '#3bb19c',
          700: '#2ca57c',
          800: '#1a8858',
          900: '#0b5e3c',
        },
        // High-contrast text colors
        text: {
          primary: '#1e293b',    // slate-800 - main headings
          secondary: '#475569',  // slate-600 - secondary text
          muted: '#64748b',      // slate-500 - subtle labels
          inverse: '#ffffff',    // white - on dark backgrounds
        }
      },
      fontFamily: {
        sans: ['Inter', 'DM Sans', 'system-ui', 'sans-serif'],
      },
      backdropBlur: {
        xs: '2px',
      }
    },
  },
  plugins: [],
}
