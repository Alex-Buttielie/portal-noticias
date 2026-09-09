"use client";
import Link from "next/link";
import { useMaisLidas } from "@/lib/queries";
import { SkeletonLista } from "@/components/ui/Estados";

function formatarData(ts: string) {
  try {
    return new Date(ts).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

// Ranking numerado das mais lidas — mesma busca e rotas, só visual +
// esqueleto elegante no carregamento e datas legíveis por máquina.
export default function MaisLidas({ limite = 5 }: { limite?: number }) {
  const { data: itens, isLoading } = useMaisLidas(limite);

  if (isLoading) {
    return (
      <section className="mais-lidas" aria-label="Mais lidas" aria-busy="true">
        <h2 className="mais-lidas-titulo">Mais lidas</h2>
        <div style={{ padding: "var(--espaco-3) var(--espaco-4)" }}>
          <SkeletonLista quantidade={limite} />
        </div>
      </section>
    );
  }

  if (!itens?.length) return null;

  return (
    <section className="mais-lidas" aria-labelledby="mais-lidas-titulo">
      <h2 id="mais-lidas-titulo" className="mais-lidas-titulo">
        Mais lidas
      </h2>
      <ol className="mais-lidas-lista">
        {itens.map((e, idx) => (
          <li key={`${e.tipo}-${e.id}`} className="mais-lidas-item">
            <span className="mais-lidas-numero" aria-hidden="true">
              {String(idx + 1).padStart(2, "0")}
            </span>
            <div className="mais-lidas-corpo">
              <Link href={`/noticia/${e.tipo}/${e.id}`} className="mais-lidas-link">
                {e.titulo}
              </Link>
              <span className="mais-lidas-meta">
                {e.categoria || "geral"} · {e.numero_fontes} fontes ·{" "}
                <time dateTime={e.timestamp}>{formatarData(e.timestamp)}</time>
              </span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
