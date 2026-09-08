"use client";
import Link from "next/link";
import { useUrgentes } from "@/lib/queries";

export default function TickerUrgente() {
  const { data: itens } = useUrgentes(6);
  if (!itens?.length) return null;
  return (
    <div className="ticker" role="region" aria-label="Urgentes">
      <span className="ticker-rotulo">URGENTE</span>
      <div className="ticker-faixa">
        <div className="ticker-trilho">
          {[...itens, ...itens].map((e, i) => (
            <Link key={`${e.tipo}-${e.id}-${i}`} href={`/noticia/${e.tipo}/${e.id}`} className="ticker-item">
              <span className="ticker-bullet">•</span> {e.titulo}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
