"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import * as api from "@/lib/api";

function formatarData(ts: string) {
  try {
    return new Date(ts).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  } catch { return ts; }
}

export default function MaisLidas({ limite = 5 }: { limite?: number }) {
  const [itens, setItens] = useState<api.FeedEntrada[]>([]);
  const [carregando, setCarregando] = useState(true);
  useEffect(() => {
    api.obterMaisLidas(limite).then(setItens).catch(() => {}).finally(() => setCarregando(false));
  }, [limite]);
  if (carregando) return <div className="mais-lidas"><p className="texto-suave">Carregando…</p></div>;
  if (!itens.length) return null;
  return (
    <div className="mais-lidas">
      <h2 className="mais-lidas-titulo">Mais lidas</h2>
      <ol className="mais-lidas-lista">
        {itens.map((e, idx) => (
          <li key={`${e.tipo}-${e.id}`} className="mais-lidas-item">
            <span className="mais-lidas-numero">{String(idx + 1).padStart(2, "0")}</span>
            <div className="mais-lidas-corpo">
              <Link href={`/noticia/${e.tipo}/${e.id}`} className="mais-lidas-link">{e.titulo}</Link>
              <span className="mais-lidas-meta">{e.categoria || "geral"} · {e.numero_fontes} fontes · {formatarData(e.timestamp)}</span>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
