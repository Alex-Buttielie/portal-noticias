import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variante = "primaria" | "secundaria" | "fantasma" | "perigo";
type Tamanho = "pequeno" | "medio" | "grande";

interface Propriedades extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante;
  tamanho?: Tamanho;
  carregando?: boolean;
  children: ReactNode;
}

export function Button({
  variante = "primaria",
  tamanho = "medio",
  carregando = false,
  disabled,
  children,
  ...resto
}: Propriedades) {
  return (
    <button
      type={resto.type ?? "button"}
      disabled={disabled ?? carregando}
      aria-busy={carregando || undefined}
      className={`botao botao--${variante} botao--${tamanho}${carregando ? " botao--carregando" : ""}`}
      {...resto}
    >
      {carregando ? "Carregando…" : children}
    </button>
  );
}
