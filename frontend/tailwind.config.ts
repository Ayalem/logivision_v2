import type { Config } from 'tailwindcss'
import animate from 'tailwindcss-animate'

// Color tokens mirror the inspo's globals.css palette. Custom semantic
// colors (electric/teal/emerald/amber/coral/purple) are exposed both as
// raw Tailwind utilities and as semantic CSS vars used by shadcn cards.
const config: Config = {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      colors: {
        // Brand palette — used directly in components.
        electric: '#2563EB',
        teal:     '#06B6D4',
        emerald:  '#10B981',
        amber:    '#F59E0B',
        coral:    '#EF4444',
        purple:   '#8B5CF6',
        // Semantic tokens — driven by CSS vars in globals.css so theme
        // switching works without a class explosion.
        border:     'hsl(var(--border) / <alpha-value>)',
        input:      'hsl(var(--input) / <alpha-value>)',
        ring:       'hsl(var(--ring) / <alpha-value>)',
        background: 'hsl(var(--background) / <alpha-value>)',
        foreground: 'hsl(var(--foreground) / <alpha-value>)',
        primary: {
          DEFAULT:    'hsl(var(--primary) / <alpha-value>)',
          foreground: 'hsl(var(--primary-foreground) / <alpha-value>)',
        },
        secondary: {
          DEFAULT:    'hsl(var(--secondary) / <alpha-value>)',
          foreground: 'hsl(var(--secondary-foreground) / <alpha-value>)',
        },
        destructive: {
          DEFAULT:    'hsl(var(--destructive) / <alpha-value>)',
          foreground: 'hsl(var(--destructive-foreground) / <alpha-value>)',
        },
        muted: {
          DEFAULT:    'hsl(var(--muted) / <alpha-value>)',
          foreground: 'hsl(var(--muted-foreground) / <alpha-value>)',
        },
        accent: {
          DEFAULT:    'hsl(var(--accent) / <alpha-value>)',
          foreground: 'hsl(var(--accent-foreground) / <alpha-value>)',
        },
        popover: {
          DEFAULT:    'hsl(var(--popover) / <alpha-value>)',
          foreground: 'hsl(var(--popover-foreground) / <alpha-value>)',
        },
        card: {
          DEFAULT:    'hsl(var(--card) / <alpha-value>)',
          foreground: 'hsl(var(--card-foreground) / <alpha-value>)',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      boxShadow: {
        soft: '0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.04)',
        glow: '0 0 0 1px rgb(37 99 235 / 0.18), 0 8px 24px -8px rgb(37 99 235 / 0.25)',
      },
      keyframes: {
        'pulse-live': { '0%,100%': { opacity: '1' }, '50%': { opacity: '0.5' } },
        'count-up':   { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        float:        { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-6px)' } },
        'glow-pulse': { '0%,100%': { opacity: '0.4' }, '50%': { opacity: '0.8' } },
        scan:         { '0%': { transform: 'translateY(-100%)' }, '100%': { transform: 'translateY(100%)' } },
      },
      animation: {
        'pulse-live': 'pulse-live 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'count-up':   'count-up 0.4s ease-out',
        float:        'float 3s ease-in-out infinite',
        'glow-pulse': 'glow-pulse 2s ease-in-out infinite',
        scan:         'scan 3s linear infinite',
      },
    },
  },
  plugins: [animate],
}

export default config
