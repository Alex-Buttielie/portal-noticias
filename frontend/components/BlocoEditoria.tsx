"use client";
import Link from "next/link";
import type { FeedEntrada } from "@/lib/api";
import { obterVisualCategoria } from "@/lib/categoryVisuals";

function formatData(ts: string) {
  try { return new Date(ts).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }); } catch { return ts; }
}

export default function BlocoEditoria({ categoria, itens, onVerTodas }: { categoria: string; itens: FeedEntrada[]; onVerTodas?: () => void }) {
  if (!itens.length) return null;
  const visual = obterVisualCategoria(categoria);
  return (
    <section className="editoria">
      <div className="editoria-cabecalho">
        <h2 className="editoria-titulo" style={{ borderColor: visual.cor }}>
          <span className="editoria-bolinha" style={{ background: visual.cor }} />
          {categoria}
        </h2>
        {onVerTodas && <button type="button" className="editoria-ver" onClick={onVerTodas}>Ver tudo →</button>}
        {!onVerTodas && <Link href={`/?categoria=${encodeURIComponent(categoria)}`} className="editoria-ver">Ver tudo →</Link>}
      </div>
      <div className="editoria-grade">
        {itens.slice(0, 3).map((e) => (
          <Link key={`${e.tipo}-${e.id}`} href={`/noticia/${e.tipo}/${e.id}`} className="editoria-card">
            <span className="editoria-tag" style={{ color: visual.cor }}>{e.categoria}</span>
            <h3 className="editoria-card-titulo">{e.titulo}</h3>
            <p className="editoria-card-resumo">{e.resumo}</p>
            <span className="editoria-meta">{formatData(e.timestamp)} · {e.numero_fontes} fontes</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
