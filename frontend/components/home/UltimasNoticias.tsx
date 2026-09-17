"use client";
import { memo, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Clock3, RefreshCw } from "lucide-react";
import { obterFeed, type FeedEntrada } from "@/lib/api";
import { ehNova, formatarHora, formatarLocalidade, timeAgo, useDebouncedValue } from "@/lib/editorial";
import { imagemNoticia } from "@/lib/imagens";
import { cn } from "@/lib/utils";

interface UltimasNoticiasProps {
  inicial: FeedEntrada[];
  limite: number;
  passo: number;
  intervaloSegundos: number;
}

/**
 * Últimas Notícias — ordem estritamente cronológica, horário visível (HH:MM),
 * selo "nova" (<60min) e atualização dinâmica (polling + botão manual).
 * Expansão inline ("mostrar mais"), sem modal.
 */
export const UltimasNoticias = memo(function UltimasNoticias({ inicial, limite, passo, intervaloSegundos }: UltimasNoticiasProps) {
  const [itens, setItens] = useState<FeedEntrada[]>(inicial);
  const [visiveis, setVisiveis] = useState(limite);
  const [atualizando, setAtualizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [atualizadoEm, setAtualizadoEm] = useState<Date | null>(null);
  const [busca, setBusca] = useState("");
  const buscaDebounced = useDebouncedValue(busca.trim().toLowerCase(), 300);

  useEffect(() => {
    setItens(inicial);
    setVisiveis(limite);
  }, [inicial, limite]);

  const atualizar = useCallback(async () => {
    setAtualizando(true);
    setErro(null);
    try {
      const resp = await obterFeed({ page_size: Math.min(60, Math.max(limite, 20)) });
      if (resp.results?.length) {
        const ordenadas = [...resp.results].sort(
          (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        );
        setItens(ordenadas);
        setAtualizadoEm(new Date());
      }
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível atualizar agora.");
    } finally {
      setAtualizando(false);
    }
  }, [limite]);

  useEffect(() => {
    if (intervaloSegundos <= 0) return;
    const id = setInterval(() => {
      if (document.visibilityState === "visible") atualizar();
    }, intervaloSegundos * 1000);
    return () => clearInterval(id);
  }, [atualizar, intervaloSegundos]);

  const lista = useMemo(() => {
    const base = buscaDebounced
      ? itens.filter((n) => `${n.titulo} ${n.resumo} ${n.categoria}`.toLowerCase().includes(buscaDebounced))
      : itens;
    return [...base]
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, visiveis);
  }, [itens, visiveis, buscaDebounced]);

  const totalFiltrado = useMemo(
    () =>
      buscaDebounced
        ? itens.filter((n) => `${n.titulo} ${n.resumo} ${n.categoria}`.toLowerCase().includes(buscaDebounced)).length
        : itens.length,
    [itens, buscaDebounced]
  );

  return (
    <section aria-label="Últimas notícias" className="flex min-h-0 flex-col rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-[var(--sombra-1)]">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-base font-bold text-[var(--cor-texto)]">
          <Clock3 className="h-4 w-4 text-[var(--cor-primaria)]" aria-hidden />
          Últimas notícias
        </h2>
        <button
          type="button"
          onClick={atualizar}
          disabled={atualizando}
          className="inline-flex items-center gap-1.5 rounded-full border border-[var(--cor-borda)] px-2.5 py-1 text-xs font-medium text-[var(--cor-texto-suave)] hover:bg-[var(--cor-fundo-elevado)] hover:text-[var(--cor-texto)] disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
        >
          <RefreshCw className={cn("h-3 w-3", atualizando && "motion-safe:animate-spin")} aria-hidden />
          {atualizando ? "Atualizando…" : "Atualizar"}
        </button>
      </div>
      {atualizadoEm && (
        <p className="mb-2 text-xs text-[var(--cor-texto-suave)]">
          Atualizado às {atualizadoEm.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
          {buscaDebounced ? ` • ${totalFiltrado} ${totalFiltrado === 1 ? "resultado" : "resultados"}` : ""}
        </p>
      )}
      <div className="relative mb-2">
        <input
          type="search"
          value={busca}
          onChange={(e) => {
            setBusca(e.target.value);
            setVisiveis(limite);
          }}
          placeholder="Filtrar últimas por palavra…"
          aria-label="Filtrar últimas notícias"
          className="h-9 w-full rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] pl-3 pr-3 text-sm text-[var(--cor-texto)] placeholder:text-[var(--cor-texto-suave)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
        />
      </div>
      {erro && (
        <p role="alert" className="mb-2 rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-xs text-[var(--cor-erro)]">
          {erro} <button type="button" onClick={atualizar} className="font-medium underline">Tentar de novo</button>
        </p>
      )}
      {atualizando && itens.length === 0 ? (
        <ol className="space-y-2" aria-label="Carregando últimas notícias">
          {Array.from({ length: 5 }).map((_, i) => (
            <li key={i} className="flex animate-pulse gap-3 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-2">
              <div className="h-12 w-16 shrink-0 rounded bg-[var(--cor-borda)]" />
              <div className="flex-1 space-y-1.5 py-1">
                <div className="h-3 w-3/4 rounded bg-[var(--cor-borda)]" />
                <div className="h-2.5 w-1/2 rounded bg-[var(--cor-borda)]" />
              </div>
            </li>
          ))}
        </ol>
      ) : lista.length === 0 ? (
        <div className="rounded-md border border-dashed border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-6 text-center">
          <p className="text-sm font-medium text-[var(--cor-texto)]">Nada por aqui ainda</p>
          <p className="mt-1 text-xs text-[var(--cor-texto-suave)]">
            Volte em instantes ou veja o <Link href="/arquivo" className="font-medium text-[var(--cor-primaria)] underline">arquivo</Link>.
          </p>
        </div>
      ) : (
        <ol className="min-h-0 flex-1 space-y-1">
          {lista.map((n) => {
            const nova = ehNova(n.timestamp);
            const local = formatarLocalidade(n);
            return (
              <li key={`ult-${n.tipo}-${n.id}`}>
                <Link
                  href={`/noticia/${n.id}`}
                  className="group flex items-center gap-3 rounded-md p-2 hover:bg-[var(--cor-fundo-elevado)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
                >
                  <span className="flex w-11 shrink-0 flex-col items-center leading-none">
                    <time dateTime={n.timestamp} className="text-sm font-bold tabular-nums text-[var(--cor-texto)]">
                      {formatarHora(n.timestamp)}
                    </time>
                    <span className="mt-0.5 text-[10px] text-[var(--cor-texto-suave)]">{timeAgo(n.timestamp)}</span>
                  </span>
                  <img src={imagemNoticia(n)} alt="" loading="lazy" decoding="async" className="h-12 w-16 shrink-0 rounded-md border border-[var(--cor-borda)] object-cover" />
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-1.5">
                      {nova && (
                        <span className="rounded-full bg-[var(--cor-primaria)] px-1.5 py-px text-[10px] font-bold uppercase tracking-wide text-[var(--cor-texto-invertido)]">
                          Nova
                        </span>
                      )}
                      <span className="truncate text-[11px] capitalize text-[var(--cor-texto-suave)]">
                        {n.categoria || "geral"}
                        {local ? ` • ${local}` : ""}
                      </span>
                    </span>
                    <span className="mt-0.5 line-clamp-2 block text-sm font-medium leading-tight text-[var(--cor-texto)] group-hover:text-[var(--cor-primaria)] motion-safe:transition-colors">
                      {n.titulo}
                    </span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ol>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-[var(--cor-borda)] pt-3">
        {visiveis < totalFiltrado && (
          <button
            type="button"
            onClick={() => setVisiveis((v) => v + passo)}
            className="rounded-full border border-[var(--cor-borda)] px-3 py-1.5 text-xs font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-fundo-elevado)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
          >
            Mostrar mais ({Math.min(passo, totalFiltrado - visiveis)} de {totalFiltrado - visiveis})
          </button>
        )}
        <Link href="/arquivo" className="text-xs font-medium text-[var(--cor-primaria)] hover:underline">
          Ver arquivo →
        </Link>
      </div>
    </section>
  );
});
