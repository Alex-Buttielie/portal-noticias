import type { ReactNode } from "react";

export type VarianteBadge = "padrao" | "sucesso" | "erro" | "neutro" | "premium";

/**
 * Rótulo de status curto, NÃO interativo (ex.: "Publicado", "Pendente",
 * "Premium") — implementation-contract.md run
 * 20260903-1134-seo-lgpd-design-system, escopo D. Só usa tokens definidos em
 * `globals.css` (`.badge`, `.badge--*`), nenhuma cor/espaçamento literal.
 * Não tem estado `disabled`/`loading` por não ser interativo — variantes
 * cobrem os estados visuais possíveis (ver `VarianteBadge`).
 */
export default function Badge({
  children,
  variante = "padrao",
}: {
  children: ReactNode;
  variante?: VarianteBadge;
}) {
  const classe = variante === "padrao" ? "badge" : `badge badge--${variante}`;
  return <span className={classe}>{children}</span>;
}
