import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variante = "primaria" | "secundaria" | "fantasma" | "perigo";
type Tamanho = "pequeno" | "medio" | "grande";

interface Propriedades extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante;
  tamanho?: Tamanho;
  carregando?: boolean;
  children: ReactNode;
}

// Botão do design system v2 — espelha `.botao`, `.botao--*` de globals.css.
// `carregando` troca o rótulo por spinner + texto e bloqueia novo clique.
export function Button({
  variante = "primaria",
  tamanho = "medio",
  carregando = false,
  disabled,
  children,
  ...resto
}: Propriedades) {
  const desabilitado = disabled ?? carregando;
  return (
    <button
      type={resto.type ?? "button"}
      disabled={desabilitado}
      aria-busy={carregando || undefined}
      aria-disabled={desabilitado || undefined}
      className={`botao botao--${variante} botao--${tamanho}`}
      {...resto}
    >
      {carregando && <span className="spinner" aria-hidden="true" />}
      <span>{carregando ? "Carregando…" : children}</span>
    </button>
  );
}
