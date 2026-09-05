"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import * as api from "@/lib/api";

export default function TickerUrgente() {
  const [itens, setItens] = useState<api.FeedEntrada[]>([]);
  useEffect(() => {
    api.obterUrgentes(6).then(setItens).catch(() => {});
  }, []);
  if (!itens.length) return null;
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
