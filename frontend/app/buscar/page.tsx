import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { SITE_NAME } from "@/lib/site";
import { AdsSlot } from "@/components/AdsSlot";
import { EstadoVazio } from "@/components/EstadoVazio";
import { BuscarReporter } from "@/components/Reporters";
import { buscarNoticias, historicoBusca, termosPopularesBusca, type ResultadoBusca } from "@/lib/api";
import { CampoBusca, ListaResultados } from "./BuscaClient";

export const metadata: Metadata = { title: `Buscar — ${SITE_NAME}`, description: `Busca no ${SITE_NAME}.` };
export const revalidate = 0;

export default async function Page({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const sp = await searchParams;
  const q = (sp.q || "").trim();
  let itens: ResultadoBusca[] = [];
  let sugestao: string | undefined;
  let populares: { termo: string; total: number }[] = [];
  let historico: string[] = [];
  // P0-08: erro de busca vira estado de erro — nunca uma lista de exemplos.
  let erroBusca = false;

  if (q) {
    try {
      const r = await buscarNoticias({ q });
      itens = r.results || [];
      sugestao = r.sugestao;
    } catch {
      itens = [];
      erroBusca = true;
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
          {erroBusca ? (
            <EstadoVazio
              tom="erro"
              titulo="Não foi possível buscar agora"
              descricao={`A busca por “${q}” falhou. Nenhum resultado foi fabricado para preencher a página.`}
              acao={{ rotulo: "Ver arquivo", href: "/arquivo" }}
            />
          ) : itens.length === 0 ? (
            <EstadoVazio
              titulo={`Nada encontrado para “${q}”`}
              descricao="Não há matéria publicada com esse termo. Tente outra palavra ou navegue pelo arquivo."
              acao={{ rotulo: "Ver arquivo", href: "/arquivo" }}
            >
              <Link href="/" className="text-sm font-medium text-[var(--cor-primaria)] underline">
                Voltar ao início
              </Link>
            </EstadoVazio>
          ) : (
            <ListaResultados itens={itens} termo={q} />
          )}
          {itens.length > 6 && <AdsSlot id="buscar-horizontal" formato="horizontal" />}
        </div>
      )}
    </div>
  );
}
