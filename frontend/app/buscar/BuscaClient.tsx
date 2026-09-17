"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { autocompleteBusca } from "@/lib/api";
import { clicarResultadoBusca } from "@/lib/recomendacao";
import type { ResultadoBusca } from "@/lib/api";

/** Campo de busca com autocomplete (sugestões reais do backend). */
export function CampoBusca({ q }: { q: string }) {
  const [valor, setValor] = useState(q);
  const [sugestoes, setSugestoes] = useState<string[]>([]);
  const [aberto, setAberto] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => setValor(q), [q]);

  function aoDigitar(v: string) {
    setValor(v);
    if (timer.current) clearTimeout(timer.current);
    if (v.trim().length < 2) {
      setSugestoes([]);
      setAberto(false);
      return;
    }
    timer.current = setTimeout(async () => {
      try {
        const r = await autocompleteBusca(v.trim());
        setSugestoes(r.sugestoes || []);
        setAberto(true);
      } catch {
        setSugestoes([]);
      }
    }, 200);
  }

  return (
    <form action="/buscar" className="relative flex gap-2" onSubmit={() => setAberto(false)}>
      <div className="relative flex-1">
        <Input
          name="q"
          value={valor}
          onChange={(e) => aoDigitar(e.target.value)}
          onFocus={() => sugestoes.length && setAberto(true)}
          onBlur={() => setTimeout(() => setAberto(false), 150)}
          placeholder="Buscar por título, assunto, autor, colunista, local…"
          aria-label="Buscar"
          autoComplete="off"
          className="h-10 bg-[var(--cor-fundo-card)]"
        />
        {aberto && sugestoes.length > 0 && (
          <ul
            role="listbox"
            aria-label="Sugestões de busca"
            className="absolute inset-x-0 top-11 z-10 overflow-hidden rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] shadow-[var(--sombra-2)]"
          >
            {sugestoes.map((s) => (
              <li key={s}>
                <Link
                  href={`/buscar?q=${encodeURIComponent(s)}`}
                  className="block truncate px-3 py-2 text-sm text-[var(--cor-texto)] hover:bg-[var(--cor-fundo-elevado)]"
                >
                  {s}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
      <Button type="submit" className="h-10 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]">
        Buscar
      </Button>
    </form>
  );
}

/** Lista de resultados com registro de clique (search_result_click). */
export function ListaResultados({ itens, termo }: { itens: ResultadoBusca[]; termo: string }) {
  return (
    <div className="grid gap-3">
      {itens.map((n) => (
        <Card key={`${n.tipo}-${n.id}`} className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <CardContent className="p-4">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="border-[var(--cor-borda)] capitalize">
                {n.categoria || "geral"}
              </Badge>
              <span className="text-xs text-[var(--cor-texto-suave)]">{n.numero_fontes} fontes</span>
              {n.trecho && (
                <span className="text-xs text-[var(--cor-texto-suave)]">• achou em {n.trecho}</span>
              )}
              {n.motivo && (
                <span className="rounded-full bg-[var(--cor-primaria-suave)] px-2 py-0.5 text-xs font-medium text-[var(--cor-primaria)]">
                  {n.motivo}
                </span>
              )}
            </div>
            <Link
              href={`/noticia/${n.id}`}
              onClick={() => clicarResultadoBusca({ tipo: n.tipo, id: n.id }, termo)}
              className="font-bold text-[var(--cor-texto)] hover:text-[var(--cor-primaria)]"
            >
              {n.titulo}
            </Link>
            <p className="mt-1 text-sm text-[var(--cor-texto-suave)]">{n.resumo}</p>
            {(n.autor || n.nome_fonte) && (
              <p className="mt-1 text-xs text-[var(--cor-texto-suave)]">
                {n.autor ? `Por ${n.autor}` : `Fonte: ${n.nome_fonte}`}
              </p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
