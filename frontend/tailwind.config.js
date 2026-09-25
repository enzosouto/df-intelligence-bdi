/** @type {import('tailwindcss').Config} */

// Sistema visual.
//
// A base é um violeta quase preto e o destaque é o magenta `#FF006A`.
//
// Sobre a base, os painéis sobem em degraus curtos de violeta. O texto NÃO
// desce em tons cada vez mais escuros: os três níveis ficam todos perto do
// branco, e a hierarquia é feita por tamanho, peso e entreletra. Texto escuro
// sobre fundo escuro é ilegível, e hierarquia não vale o custo de ninguém
// conseguir ler a cota.
//
// As seis cores de domínio ficam espalhadas pela roda (0°, 190°, 145°, 30°,
// 265°, mais o branco) para que duas séries num mesmo gráfico nunca se
// confundam. O magenta acumula duas funções de propósito: é o destaque da
// interface — foco, navegação ativa, retícula — e é a cor da segurança, o
// domínio que mais pede atenção. Os dois registros nunca aparecem no mesmo
// lugar: um é moldura, o outro é marca de dado.
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        // Não se chama `base`: `text-base` já é o utilitário de tamanho de
        // fonte do Tailwind, e as duas regras coexistiriam — todo título com
        // `text-base` sairia pintado da cor do fundo.
        night: '#060010',
        surface: '#0C0320',
        elevated: '#14082C',
        line: '#2C1549',
        ink: '#FFFFFF',
        muted: '#DCD5EC',
        faint: '#BFB4D6',

        accent: '#FF006A',

        // Uma cor por domínio, igual em mapa, gráfico, tabela e legenda.
        population: '#FFFFFF',
        security: '#FF006A',
        health: '#00D4FF',
        education: '#7CFFB2',
        mobility: '#FF9A3D',
        weather: '#A86BFF',
        warn: '#FFC93D',
      },
      fontFamily: {
        // Archivo em largura expandida: a letra ocupa o eixo como a cidade.
        display: ['Archivo', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        sans: ['"IBM Plex Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      letterSpacing: {
        plan: '0.22em',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-500px 0' },
          '100%': { backgroundPosition: '500px 0' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.25' },
        },
      },
      animation: {
        shimmer: 'shimmer 1.6s linear infinite',
        blink: 'blink 1.1s steps(2, end) infinite',
      },
    },
  },
  plugins: [],
}
