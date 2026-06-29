import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: '#FAF7F5',
        surface: '#FFFFFF',
        'border-col': '#E7E2DF',
        primary: '#111827',
        secondary: '#6B7280',
        accent: '#D77855',
        'accent-soft': '#F8E8DF',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      keyframes: {
        fadeInUp: {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        fadeInUp: 'fadeInUp 0.22s ease-out forwards',
      },
    },
  },
  plugins: [],
}

export default config
