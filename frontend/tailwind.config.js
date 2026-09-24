/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        // Fundo em camadas: quanto mais alto o elemento, mais claro.
        base: '#08090B',
        surface: '#0F1115',
        elevated: '#15181E',
        line: '#222732',
        ink: '#ECEFF4',
        muted: '#98A2B3',
        faint: '#5D6675',

        // Uma cor por domínio, usada de forma consistente em mapa,
        // gráficos, cards e badges.
        population: '#5EE6C5',
        security: '#FF6B81',
        health: '#4CC2FF',
        weather: '#A98BFF',
        education: '#C3E86B',
        warn: '#F5A524',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['"Space Grotesk"', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 0 0 rgba(255,255,255,0.03) inset, 0 12px 32px -18px rgba(0,0,0,0.9)',
        glow: '0 0 0 1px rgba(94,230,197,0.25), 0 0 40px -12px rgba(94,230,197,0.35)',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-500px 0' },
          '100%': { backgroundPosition: '500px 0' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.45s cubic-bezier(0.22, 1, 0.36, 1) both',
        shimmer: 'shimmer 1.6s linear infinite',
      },
    },
  },
  plugins: [],
}
