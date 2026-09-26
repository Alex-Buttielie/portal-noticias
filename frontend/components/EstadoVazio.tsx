import type { ReactNode } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Estado honesto de lista vazia / erro de carga.
 *
 * Regra editorial (P0-08): quando a API falha ou não devolve nada, mostramos
 * este estado — nunca uma manchete, um número ou um preço inventado. O texto
 * é anunciado por leitores de tela via `role="status"` (neutro) ou
 * `role="alert"` (erro), sem quebrar o grid em que o bloco foi inserido.
 */
export function EstadoVazio({
  titulo,
  descricao,
  tom = "neutro",
  acao,
  onTentarDeNovo,
  rotuloTentarDeNovo = "Tentar de novo",
  children,
  className,
}: {
  titulo: string;
  descricao?: ReactNode;
  tom?: "neutro" | "erro";
  acao?: { rotulo: string; href: string };
  onTentarDeNovo?: () => void;
  rotuloTentarDeNovo?: string;
  children?: ReactNode;
  className?: string;
}) {
  const erro = tom === "erro";
  return (
    <div
      role={erro ? "alert" : "status"}
      aria-live={erro ? "assertive" : "polite"}
      data-tom={tom}
      className={cn(
        "rounded-[var(--raio-lg)] border p-6 text-center",
        erro
          ? "border-[var(--cor-erro)] bg-[var(--cor-erro-suave)]"
          : "border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]",
        className
      )}
    >
      <p className={cn("text-sm font-semibold", erro ? "text-[var(--cor-erro)]" : "text-[var(--cor-texto)]")}>
        {titulo}
      </p>
      {descricao ? (
        <p className={cn("mt-1 text-sm", erro ? "text-[var(--cor-erro)]" : "text-[var(--cor-texto-suave)]")}>
          {descricao}
        </p>
      ) : null}
      {children ? <div className="mt-3">{children}</div> : null}
      {acao || onTentarDeNovo ? (
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          {onTentarDeNovo ? (
            <Button
              type="button"
              variant="outline"
              onClick={onTentarDeNovo}
              className="min-h-[44px] border-[var(--cor-borda)]"
            >
              {rotuloTentarDeNovo}
            </Button>
          ) : null}
          {acao ? (
            <Button asChild variant="outline" className="min-h-[44px] border-[var(--cor-borda)]">
              <Link href={acao.href}>{acao.rotulo}</Link>
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default EstadoVazio;
