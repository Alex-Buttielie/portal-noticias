import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { EntradaRanqueda } from "@/lib/api";

/**
 * FRENTE 3 — Destaques do Dia dinâmicos (relevância editorial + acessos +
 * crescimento + pesquisas + engajamento + região, com override manual).
 * Lista vem pronta do backend (`GET /api/feed/destaques/`); aqui só exibe.
 * Sem destaques, não renderiza nada (nunca inventa conteúdo).
 */
export function DestaquesDia({ destaques }: { destaques: EntradaRanqueda[] }) {
  if (!destaques.length) return null;
  return (
    <section aria-label="Destaques do dia" className="mb-6 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-[var(--sombra-1)]">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-bold tracking-tight text-[var(--cor-texto)]">Destaques do dia</h2>
        <span className="text-xs text-[var(--cor-texto-suave)]">atualizado ao longo do dia</span>
      </div>
      <ol className="grid gap-3 md:grid-cols-5">
        {destaques.map((d, i) => (
          <li key={`${d.tipo}-${d.id}`}>
            <Card className="h-full border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]">
              <CardContent className="flex h-full flex-col gap-1.5 p-3">
                <span className="flex items-center gap-2 text-xs text-[var(--cor-texto-suave)]">
                  <span className="font-bold text-[var(--cor-primaria)]">{i + 1}</span>
                  <span className="capitalize">{d.categoria || "geral"}</span>
                  {d.motivo && (
                    <Badge variant="outline" className="border-[var(--cor-borda)] text-[10px]">
                      {d.motivo}
                    </Badge>
                  )}
                </span>
                <Link
                  href={`/noticia/${d.id}`}
                  className="line-clamp-3 text-sm font-bold leading-snug text-[var(--cor-texto)] hover:text-[var(--cor-primaria)]"
                >
                  {d.titulo}
                </Link>
                <span className="mt-auto text-[11px] text-[var(--cor-texto-suave)]">
                  {d.numero_fontes > 1 ? `${d.numero_fontes} fontes` : d.nome_fonte || ""}
                  {d.override === "destaque" ? " • escolha editorial" : ""}
                </span>
              </CardContent>
            </Card>
          </li>
        ))}
      </ol>
    </section>
  );
}
