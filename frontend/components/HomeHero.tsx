"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import * as api from "@/lib/api";
import { useFeed } from "@/lib/queries";
import { HeroPrincipal, HeroSecundario } from "@/components/Hero";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const INTERVALO_VERIFICACAO_NOVIDADES_MS = 60000;

function chaveDaEntrada(e: api.FeedEntrada): string {
  return `${e.tipo}-${e.id}`;
}

interface HomeHeroProps {
  inicial: {
    feed: api.FeedResposta;
    urgentes: api.FeedEntrada[];
    maisLidas: api.FeedEntrada[];
    onboarding: { interesses: string[] };
  };
}

export default function HomeHero({ inicial }: HomeHeroProps) {
  const [novidadeDisponivel, setNovidadeDisponivel] = useState(false);
  const primeiraChaveRef = useRef<string | null>(null);
  const feed = useFeed({});

  useEffect(() => {
    primeiraChaveRef.current = inicial.feed.results[0] ? chaveDaEntrada(inicial.feed.results[0]) : null;
  }, [inicial.feed.results]);

  useEffect(() => {
    const verificar = () => {
      if (document.hidden) return;
      api
        .obterFeed({ page: 1 })
        .then((r) => {
          const chaveNova = r.results[0] ? chaveDaEntrada(r.results[0]) : null;
          if (chaveNova && chaveNova !== primeiraChaveRef.current) setNovidadeDisponivel(true);
        })
        .catch(() => {});
    };
    const id = window.setInterval(verificar, INTERVALO_VERIFICACAO_NOVIDADES_MS);
    return () => window.clearInterval(id);
  }, []);

  const [principal, ...secundarias] = inicial.urgentes;
  const temSinais = inicial.onboarding.interesses.length > 0;

  return (
    <>
      {inicial.feed.exibir_publicidade && (
        <div className="rounded-md border border-[var(--cor-borda)] border-l-[3px] border-l-[var(--cor-alerta)] bg-[var(--cor-fundo-elevado)] px-3 py-2 text-sm text-[var(--cor-texto-suave)]">
          Espaço publicitário — assine o{" "}
          <Link href="/planos" className="font-semibold text-[var(--cor-primaria)] underline-offset-2 hover:underline">
            Premium
          </Link>{" "}
          para navegar sem anúncios.
        </div>
      )}
      {novidadeDisponivel && (
        <div className="sticky top-16 z-[var(--z-banner)] mb-4 flex justify-center" aria-live="polite">
          <Button
            type="button"
            onClick={() => {
              setNovidadeDisponivel(false);
              void feed.refetch();
              window.scrollTo({ top: 0 });
            }}
            className="rounded-full shadow-md"
          >
            Novas notícias disponíveis — atualizar
          </Button>
        </div>
      )}
      {principal && <HeroPrincipal entrada={principal} />}
      {secundarias.length > 0 && (
        <section className="mt-6 min-w-0 space-y-4" aria-label="Outras urgentes">
          <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {secundarias.slice(0, 3).map((entrada, i) => (
              <HeroSecundario key={`${entrada.tipo}-${entrada.id}`} entrada={entrada} posicao={i + 2} />
            ))}
          </div>
        </section>
      )}
      <header className={cn("mb-6 min-w-0 space-y-2")}>
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)]">
          {temSinais ? "Feito para o seu gosto" : "Cobertura ao vivo"}
        </p>
        <h1 className="font-[var(--fonte-titulo)] text-[clamp(2rem,5vw,3.2rem)] font-extrabold leading-[1.05] tracking-tight text-wrap-balance">
          Seu rio
        </h1>
        <p className="max-w-[62ch] break-words text-sm leading-relaxed text-[var(--cor-texto-suave)]">
          {temSinais
            ? "A ordem abaixo segue os seus interesses e leituras — nunca uma escolha editorial opaca."
            : "Ordem cronológica, igual para todas as pessoas. Personalize seu feed no onboarding para o rio se moldar a você."}
        </p>
      </header>
    </>
  );
}
