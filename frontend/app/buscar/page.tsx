import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { SITE_NAME } from "@/lib/site";
import { AdsSlot } from "@/components/AdsSlot";
import { BuscarReporter } from "@/components/Reporters";
import { buscarNoticias, historicoBusca, termosPopularesBusca, type ResultadoBusca } from "@/lib/api";
import { CampoBusca, ListaResultados } from "./BuscaClient";

export const metadata: Metadata = { title: `Buscar — ${SITE_NAME}`, description: `Busca no ${SITE_NAME}.` };
export const revalidate = 0;

/**
 * Busca.
 *
 * Havia um `MOCK` com um resultado "Resultados — busque por política,
 * economia..." que substituía a busca real quando a chamada lançava. O efeito
 * era pior do que "parece um resultado": o título continha a query do usuário e
 * o resultado NÃO vinha do índice, então uma busca por termo técnico ou por
 * cidade retornava uma "notícia" que não existe, com link para `/noticia/201`.
 * Falha de busca agora é falha de busca, com o código de correlação.
 */
export default async function Page({ searchParams }: { searchParams: { q?: string } }) {
  const q = (searchParams.q || "").trim();
  let itens: ResultadoBusca[] = [];
  let sugestao: string | undefined;
  let populares: { termo: string; total: number }[] = [];
  let historico: string[] = [];
  let buscaFalhou = false;
  let requestId: string | null = null;

  if (q) {
    try {
      const r = await buscarNoticias({ q });
      itens = r.results || [];
      sugestao = r.sugestao;
    } catch (erro) {
      buscaFalhou = true;
      if (erro instanceof Error) requestId = (erro as { requestId?: string | null }).requestId ?? null;
    }
  } else {
    try {
      const [pop, hist] = await Promise.all([
        termosPopularesBusca().catch(() => ({ termos: [] as { termo: string; total: number }[] })),
        historicoBusca().catch(() => ({ historico: [] as string[] })),
      ]);
      populares = pop.termos || [];
      historico = hist.historico || [];
    } catch {
      /* descoberta vazia não quebra a página */
    }
  }

  return (
    <div className="space-y-4">
      {q && <BuscarReporter termo={q} resultados={itens.length} />}
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4">
        <div className="hud-line mb-3" aria-hidden />
        <h1 className="text-xl font-bold text-[var(--cor-texto)]">Buscar</h1>
        <p className="text-sm text-[var(--cor-texto-suave)]">
          Título, conteúdo, categoria, autor, colunista, fonte ou local.
        </p>
        <div className="mt-3">
          <CampoBusca q={q} />
        </div>
      </div>

      {!q && (
        <div className="grid gap-3 md:grid-cols-2">
          <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]">
            <CardContent className="p-4">
              <p className="mb-2 text-sm font-bold text-[var(--cor-texto)]">Em alta nas buscas</p>
              {populares.length === 0 ? (
                <p className="text-sm text-[var(--cor-texto-suave)]">
                  Ex.: <Link href="/buscar?q=política" className="text-[var(--cor-primaria)] hover:underline">política</Link>,{" "}
                  <Link href="/buscar?q=tecnologia" className="text-[var(--cor-primaria)] hover:underline">tecnologia</Link>.
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {populares.map((t) => (
                    <Link
                      key={t.termo}
                      href={`/buscar?q=${encodeURIComponent(t.termo)}`}
                      className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 py-1 text-sm text-[var(--cor-texto)] hover:border-[var(--cor-primaria)]"
                    >
                      {t.termo}
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
          <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]">
            <CardContent className="p-4">
              <p className="mb-2 text-sm font-bold text-[var(--cor-texto)]">Suas buscas recentes</p>
              {historico.length === 0 ? (
                <p className="text-sm text-[var(--cor-texto-suave)]">Nenhuma busca recente neste aparelho.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {historico.map((h) => (
                    <Link
                      key={h}
                      href={`/buscar?q=${encodeURIComponent(h)}`}
                      className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 py-1 text-sm text-[var(--cor-texto)] hover:border-[var(--cor-primaria)]"
                    >
                      {h}
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {q && (
        <div className="space-y-3">
          {buscaFalhou ? (
            <div role="alert" className="rounded-[var(--raio-lg)] border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] p-4">
              <p className="text-sm font-semibold text-[var(--cor-texto)]">A busca está indisponível.</p>
              <p className="mt-1 text-sm text-[var(--cor-texto-suave)]">
                Não conseguimos consultar o índice agora. Não mostramos resultados de exemplo para a sua busca.
              </p>
              {requestId ? <p className="mt-2 text-xs text-[var(--cor-texto-suave)]">Código de suporte: {requestId}</p> : null}
            </div>
          ) : (
            <>
              <p className="text-sm text-[var(--cor-texto-suave)]">
                {itens.length} resultado(s) para <span className="font-semibold text-[var(--cor-texto)]">“{q}”</span>
              </p>
              {sugestao && (
                <p className="text-sm text-[var(--cor-texto-suave)]">
                  Você quis dizer{" "}
                  <Link href={`/buscar?q=${encodeURIComponent(sugestao)}`} className="font-medium text-[var(--cor-primaria)] underline">
                    {sugestao}
                  </Link>
                  ?
                </p>
              )}
              {itens.length === 0 ? (
                <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]">
                  <CardContent className="p-6 text-center text-sm text-[var(--cor-texto-suave)]">
                    Nenhum resultado para “{q}”. <Link href="/arquivo" className="font-medium text-[var(--cor-primaria)] underline">Ver arquivo</Link> •{" "}
                    <Link href="/" className="font-medium text-[var(--cor-primaria)] underline">Voltar ao início</Link>
                  </CardContent>
                </Card>
              ) : (
                <ListaResultados itens={itens} termo={q} />
              )}
            </>
          )}
          {itens.length > 0 && <AdsSlot id="buscar-infeed" formato="in-feed" className="my-6" />}
          {itens.length > 6 && <AdsSlot id="buscar-horizontal" formato="horizontal" />}
        </div>
      )}
    </div>
  );
}
