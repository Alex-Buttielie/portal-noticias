import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        border: "var(--cor-borda)",
        input: "var(--cor-borda)",
        ring: "var(--cor-foco)",
        background: "var(--cor-fundo)",
        foreground: "var(--cor-texto)",
        primary: {
          DEFAULT: "var(--cor-primaria)",
          hover: "var(--cor-primaria-hover)",
          soft: "var(--cor-primaria-suave)",
          foreground: "var(--cor-texto-invertido)",
        },
        secondary: {
          DEFAULT: "var(--cor-secundaria)",
          hover: "var(--cor-secundaria-hover)",
          soft: "var(--cor-secundaria-suave)",
          foreground: "var(--cor-texto-invertido)",
        },
        destructive: {
          DEFAULT: "var(--cor-erro)",
          hover: "var(--cor-erro-hover)",
          soft: "var(--cor-erro-suave)",
          foreground: "var(--cor-texto-invertido)",
        },
        success: {
          DEFAULT: "var(--cor-sucesso)",
          hover: "var(--cor-sucesso-hover)",
          soft: "var(--cor-sucesso-suave)",
          foreground: "var(--cor-texto-invertido)",
        },
        warning: {
          DEFAULT: "var(--cor-alerta)",
          hover: "var(--cor-alerta-hover)",
          soft: "var(--cor-alerta-suave)",
          foreground: "var(--cor-texto-invertido)",
        },
        premium: {
          DEFAULT: "var(--cor-premium)",
          hover: "var(--cor-premium-hover)",
          soft: "var(--cor-premium-suave)",
          foreground: "var(--cor-texto-invertido)",
        },
        muted: {
          DEFAULT: "var(--cor-fundo-elevado)",
          foreground: "var(--cor-texto-suave)",
        },
        accent: {
          DEFAULT: "var(--cor-destaque)",
          hover: "var(--cor-destaque-hover)",
          soft: "var(--cor-destaque-suave)",
          foreground: "var(--cor-texto-invertido)",
        },
        card: {
          DEFAULT: "var(--cor-fundo-card)",
          foreground: "var(--cor-texto)",
        },
        skeleton: {
          base: "var(--cor-skeleton-base)",
          highlight: "var(--cor-skeleton-brilho)",
        },
        glass: "var(--vidro)",
        "brand-gradient": "var(--gradiente-marca)",
        shadow: "rgba(var(--cor-sombra), <alpha-value>)",
      },
      spacing: {
        "0": "var(--espaco-0)",
        "1": "var(--espaco-1)",
        "1.5": "var(--espaco-1-5)",
        "2": "var(--espaco-2)",
        "2.5": "var(--espaco-2-5)",
        "3": "var(--espaco-3)",
        "4": "var(--espaco-4)",
        "5": "var(--espaco-5)",
        "6": "var(--espaco-6)",
        "7": "var(--espaco-7)",
        "8": "var(--espaco-8)",
      },
      borderRadius: {
        sm: "var(--raio-sm)",
        md: "var(--raio-md)",
        lg: "var(--raio-lg)",
        full: "var(--raio-completo)",
      },
      boxShadow: {
        "1": "var(--sombra-1)",
        "2": "var(--sombra-2)",
        "3": "var(--sombra-3)",
      },
      zIndex: {
        "content-elevated": "var(--z-conteudo-elevado)",
        header: "var(--z-cabecalho)",
        "floating-panel": "var(--z-painel-flutuante)",
        banner: "var(--z-banner)",
        "modal-backdrop": "var(--z-modal-fundo)",
        modal: "var(--z-modal)",
        toast: "var(--z-toast)",
        cookies: "var(--z-cookies)",
      },
      fontSize: {
        xs: ["var(--fonte-tamanho-xs)", { lineHeight: "var(--linha-altura-padrao)", fontWeight: "var(--fonte-peso-normal)" }],
        sm: ["var(--fonte-tamanho-sm)", { lineHeight: "var(--linha-altura-padrao)", fontWeight: "var(--fonte-peso-normal)" }],
        base: ["var(--fonte-tamanho-md)", { lineHeight: "var(--linha-altura-padrao)", fontWeight: "var(--fonte-peso-normal)" }],
        lg: ["var(--fonte-tamanho-lg)", { lineHeight: "var(--linha-altura-padrao)", fontWeight: "var(--fonte-peso-medio)" }],
        xl: ["var(--fonte-tamanho-xl)", { lineHeight: "var(--linha-altura-compacta)", fontWeight: "var(--fonte-peso-negrito)" }],
        "2xl": ["var(--fonte-tamanho-xxl)", { lineHeight: "var(--linha-altura-compacta)", fontWeight: "var(--fonte-peso-negrito)" }],
      },
      fontWeight: {
        normal: "var(--fonte-peso-normal)",
        medium: "var(--fonte-peso-medio)",
        bold: "var(--fonte-peso-negrito)",
      },
      lineHeight: {
        compact: "var(--linha-altura-compacta)",
        normal: "var(--linha-altura-padrao)",
        relaxed: "var(--linha-altura-solta)",
      },
      transitionDuration: {
        fast: "var(--duracao-rapida)",
        normal: "var(--duracao-normal)",
        slow: "var(--duracao-lenta)",
      },
      transitionTimingFunction: {
        default: "var(--curva-padrao)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "slide-in-from-left": {
          from: { transform: "translateX(-100%)" },
          to: { transform: "translateX(0)" },
        },
        "slide-out-to-left": {
          from: { transform: "translateX(0)" },
          to: { transform: "translateX(-100%)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "fade-out": {
          from: { opacity: "1" },
          to: { opacity: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down var(--duracao-normal) var(--curva-padrao)",
        "accordion-up": "accordion-up var(--duracao-normal) var(--curva-padrao)",
        "slide-in-left": "slide-in-from-left var(--duracao-normal) var(--curva-padrao)",
        "slide-out-left": "slide-out-to-left var(--duracao-normal) var(--curva-padrao)",
        "fade-in": "fade-in var(--duracao-rapida) var(--curva-padrao)",
        "fade-out": "fade-out var(--duracao-rapida) var(--curva-padrao)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;