import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class", '[data-theme="dark"]'],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
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
          foreground: "#ffffff",
          hover: "var(--cor-primaria-hover)",
          suave: "var(--cor-primaria-suave)",
        },
        destaque: {
          DEFAULT: "var(--cor-destaque)",
          hover: "var(--cor-destaque-hover)",
          suave: "var(--cor-destaque-suave)",
        },
        destructive: {
          DEFAULT: "var(--cor-erro)",
          foreground: "#ffffff",
        },
        sucesso: {
          DEFAULT: "var(--cor-sucesso)",
        },
        premium: {
          DEFAULT: "var(--cor-premium)",
          foreground: "#ffffff",
        },
        muted: {
          DEFAULT: "var(--cor-fundo-elevado)",
          foreground: "var(--cor-texto-suave)",
        },
        card: {
          DEFAULT: "var(--cor-fundo-card)",
          foreground: "var(--cor-texto)",
        },
        popover: {
          DEFAULT: "var(--cor-fundo-elevado)",
          foreground: "var(--cor-texto)",
        },
        secondary: {
          DEFAULT: "var(--cor-fundo-elevado)",
          foreground: "var(--cor-texto)",
        },
        accent: {
          DEFAULT: "var(--cor-primaria-suave)",
          foreground: "var(--cor-primaria)",
        },
        // aliases diretos para tokens legados
        fundo: "var(--cor-fundo)",
        "fundo-elevado": "var(--cor-fundo-elevado)",
        texto: "var(--cor-texto)",
        "texto-suave": "var(--cor-texto-suave)",
        borda: "var(--cor-borda)",
        foco: "var(--cor-foco)",
        erro: "var(--cor-erro)",
      },
      borderRadius: {
        sm: "var(--raio-sm)",
        md: "var(--raio-md)",
        lg: "var(--raio-lg)",
        full: "var(--raio-completo)",
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
      boxShadow: {
        "1": "var(--sombra-1)",
        "2": "var(--sombra-2)",
        "3": "var(--sombra-3)",
      },
      zIndex: {
        "conteudo-elevado": "var(--z-conteudo-elevado)",
        cabecalho: "var(--z-cabecalho)",
        "painel-flutuante": "var(--z-painel-flutuante)",
        banner: "var(--z-banner)",
        "modal-fundo": "var(--z-modal-fundo)",
        modal: "var(--z-modal)",
        toast: "var(--z-toast)",
        cookies: "var(--z-cookies)",
      },
      fontFamily: {
        corpo: ["var(--fonte-corpo)"],
        titulo: ["var(--fonte-titulo)"],
      },
      fontSize: {
        xs: "var(--fonte-tamanho-xs)",
        sm: "var(--fonte-tamanho-sm)",
        md: "var(--fonte-tamanho-md)",
        lg: "var(--fonte-tamanho-lg)",
        xl: "var(--fonte-tamanho-xl)",
        "2xl": "var(--fonte-tamanho-xxl)",
      },
      maxWidth: {
        leitura: "var(--largura-leitura)",
        "conteudo-estreito": "var(--largura-conteudo-estreito)",
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
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
