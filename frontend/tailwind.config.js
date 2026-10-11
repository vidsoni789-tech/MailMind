/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        cream: {
          bg: '#F7F5F0',
          sidebar: '#FBFAF7',
          panel: '#FBFAF7',
          card: '#FFFFFF',
          input: '#FFFFFF',
          border: '#E7E4DC',
          'border-subtle': '#EFECE6',
          hover: '#F0EEE7',
          'nav-active': '#EAEFFF',
          'nav-hover': '#F5F3EC',
        },
        text: {
          primary: '#252821',
          secondary: '#74766F',
          muted: '#92938C',
        },
        // Safeguard alias: maps legacy dark tokens to warm cream & white surfaces
        dark: {
          bg: '#F7F5F0',
          panel: '#FBFAF7',
          card: '#FFFFFF',
          border: '#E7E4DC',
          hover: '#F0EEE7',
          subtle: '#FBFAF7',
        },
        accent: {
          blue: '#4263EB',
          'blue-hover': '#3451D1',
          green: '#23845B',
          yellow: '#A66A12',
          amber: '#A66A12',
          red: '#C24141',
          purple: '#4263EB',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        subtle: '0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 3px 1px rgba(0, 0, 0, 0.02)',
        card: '0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.03)',
        dropdown: '0 4px 12px 0 rgba(0, 0, 0, 0.06), 0 2px 4px 0 rgba(0, 0, 0, 0.03)',
      },
    },
  },
  plugins: [],
}
