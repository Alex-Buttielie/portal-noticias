"use client";

import type { ReactNode } from "react";

/**
 * Tag interativa (selecionável e/ou removível) — ex.: filtro ativo, interesse
 * selecionado no onboarding (implementation-contract.md run
 * 20260903-1134-seo-lgpd-design-system, escopo D). O clique principal e o
 * botão de remover são elementos irmãos, nunca um `<button>` aninhado dentro
 * de outro (HTML inválido e confuso para leitor de tela) — a raiz é um
 * `<span>` não interativo que só agrupa visualmente os dois.
 */
export default function Chip({
  children,
  selecionado = false,
  disabled = false,
  aoClicar,
  aoRemover,
  removerRotulo,
}: {
  children: ReactNode;
  selecionado?: boolean;
  disabled?: boolean;
  aoClicar?: () => void;
  aoRemover?: () => void;
  /** Texto acessível do botão de remover (ex.: "Remover filtro Economia"). */
  removerRotulo?: string;
}) {
  const classe = selecionado ? "chip chip--selecionado" : "chip";
  const conteudo = <span>{children}</span>;

  return (
    <span className={classe} aria-disabled={disabled || undefined}>
      {aoClicar ? (
        <button
          type="button"
          style={{ all: "unset", cursor: disabled ? "not-allowed" : "pointer" }}
          aria-pressed={selecionado}
          disabled={disabled}
          onClick={aoClicar}
        >
          {conteudo}
        </button>
      ) : (
        conteudo
      )}
      {aoRemover && (
        <button
          type="button"
          className="chip-remover"
          aria-label={removerRotulo || "Remover"}
          disabled={disabled}
          onClick={aoRemover}
        >
          ✕
        </button>
      )}
    </span>
  );
}
