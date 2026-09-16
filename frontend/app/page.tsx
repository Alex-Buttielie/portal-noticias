import type { Metadata } from "next";
import { Suspense } from "react";
import * as api from "@/lib/api";
import { SITE_URL, SITE_DESCRIPTION } from "@/lib/site";
import { cn } from "@/lib/utils";
import HomeHero from "@/components/HomeHero";
import HomeSidebar from "@/components/HomeSidebar";
import BlocoEditoria from "@/components/BlocoEditoria";
import { CartaoEsqueleto } from "@/components/CartaoEsqueleto";

export const metadata: Metadata = {
  title: "Portal de Notícias — Toda a informação que importa",
  description: SITE_DESCRIPTION,
  alternates: { canonical: SITE_URL },
  openGraph: {
    type: "website",
    title: "Portal de Notícias",
    description: SITE_DESCRIPTION,
    url: SITE_URL,
    siteName: "Portal de Notícias",
    images: [{ url: "/og-padrao.svg", width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Portal de Notícias",
    description: SITE_DESCRIPTION,
    images: ["/og-padrao.svg"],
  },
};

async function getInitialData() {
  const [feed, urgentes, maisLidas] = await Promise.all([
    api.obterFeed({ page: 1 }).catch(() => null),
    api.obterUrgentes(6).catch(() => [] as api.FeedEntrada[]),
    api.obterMaisLidas(5).catch(() => [] as api.FeedEntrada[]),
  ]);

  return {
    feed: feed ?? { count: 0, next: null, previous: null, results: [], exibir_publicidade: true },
    urgentes: urgentes ?? [],
    maisLidas: maisLidas ?? [],
    onboarding: { interesses: [] as string[] },
  };
}

function agruparPorCategoria(itens: api.FeedEntrada[]): Array<{ categoria: string; itens: api.FeedEntrada[] }> {
  const grupos = new Map<string, api.FeedEntrada[]>();
  for (const item of itens) {
    const cat = (item.categoria || "geral").trim() || "geral";
    const lista = grupos.get(cat);
    if (lista) lista.push(item);
    else grupos.set(cat, [item]);
  }
  return [...grupos.entries()].map(([categoria, lista]) => ({ categoria, itens: lista }));
}

function HomeSkeleton() {
  return (
    <div className="min-w-0 w-full max-w-full space-y-4 overflow-hidden" aria-hidden="true">
      <CartaoEsqueleto variant="default" />
      <div className="grid w-full max-w-full grid-cols-1 items-start gap-4 overflow-hidden sm:gap-6 lg:grid-cols-[minmax(0,1fr)_330px]">
        <div className="min-w-0 w-full max-w-full space-y-8 overflow-hidden">
          <CartaoEsqueleto variant="horizontal" />
          <CartaoEsqueleto variant="horizontal" />
        </div>
        <div className="flex min-w-0 w-full max-w-full flex-col gap-5 self-start overflow-hidden">
          <CartaoEsqueleto variant="compact" />
          <CartaoEsqueleto variant="compact" />
        </div>
      </div>
      <span className="sr-only" role="status">
        Carregando página inicial…
      </span>
    </div>
  );
}

export default async function PaginaHome() {
  const initialData = await getInitialData();
  const blocos = agruparPorCategoria(initialData.feed.results).slice(0, 4);

  return (
    <main id="conteudo-principal" className="min-w-0 w-full max-w-full space-y-6">
      <Suspense fallback={<HomeSkeleton />}>
        <HomeHero inicial={initialData} />
        <div
          className={cn(
            "grid w-full max-w-full grid-cols-1 items-start gap-4 overflow-hidden sm:gap-6",
            "lg:grid-cols-[minmax(0,1fr)_330px]"
          )}
        >
          <div className="min-w-0 w-full max-w-full space-y-8 overflow-hidden">
            {blocos.map((bloco) => (
              <BlocoEditoria key={bloco.categoria} categoria={bloco.categoria} itens={bloco.itens} carrosselMobile />
            ))}
          </div>
          <aside
            className="flex min-w-0 w-full max-w-full flex-col gap-5 self-start overflow-hidden lg:sticky lg:top-24"
            aria-label="Conteúdo relacionado"
          >
            <HomeSidebar inicial={initialData} />
          </aside>
        </div>
      </Suspense>
    </main>
  );
}
