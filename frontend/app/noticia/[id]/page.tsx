import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { SITE_NAME, SITE_URL } from "@/lib/site";
import { newsArticleJsonLd } from "@/lib/schema";
import { obterDetalheCluster, obterDetalheItem, obterFeed, ApiError, type FeedDetalhe } from "@/lib/api";
import { imagemNoticia } from "@/lib/imagens";
import { LeituraPremium } from "../LeituraPremium";
import { NoticiaReporter } from "@/components/Reporters";
import { CoberturaCompleta } from "@/components/CoberturaCompleta";
import { NoticiaIndisponivel } from "@/components/NoticiaIndisponivel";

/**
 * Três estados, que não podem ser confundidos uns com os outros:
 *
 * - `detalhe`      — a notícia existe;
 * - `inexistente`  — o backend respondeu 404: `notFound()` honesto. Antes
 *   `getDetalhe` devolvia, no lugar do `null`, um artigo de demonstração com
 *   título "Notícia #N — conteúdo de demonstração" e fonte "Fonte Exemplo", e a
 *   página ainda injetava `newsArticleJsonLd` com esse dado — o Google recebia
 *   NewsArticle de uma notícia inventada;
 * - `indisponivel` — o backend está fora (5xx, timeout, conexão recusada). Vira
 *   `NoticiaIndisponivel` com o código de suporte, e NUNCA 404: um 404 aqui
 *   mandaria o leitor e o crawler a concluírem que a URL foi removida.
 */
type ResultadoDetalhe =
  | { tipo: "detalhe"; dados: FeedDetalhe }
  | { tipo: "inexistente" }
  | { tipo: "indisponivel"; requestId: string | null; mensagem: string };

function classificar(erro: unknown): { tipo: "inexistente" } | { tipo: "indisponivel"; requestId: string | null; mensagem: string } {
  if (erro instanceof ApiError && erro.status === 404) return { tipo: "inexistente" };
  return {
    tipo: "indisponivel",
    requestId: erro instanceof ApiError ? erro.requestId : null,
    mensagem: erro instanceof Error ? erro.message : "Falha inesperada ao consultar a notícia.",
  };
}

async function getDetalhe(id: string): Promise<ResultadoDetalhe> {
  try {
    return { tipo: "detalhe", dados: await obterDetalheCluster(id) };
  } catch (erro) {
    const falha = classificar(erro);
    if (falha.tipo === "indisponivel") return falha;
  }
  try {
    return { tipo: "detalhe", dados: await obterDetalheItem(id) };
  } catch (erro) {
    return classificar(erro);
  }
}

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const resultado = await getDetalhe(params.id);
  const t = resultado.tipo === "detalhe" ? resultado.dados.titulo : `Notícia #${params.id} — ${SITE_NAME}`;
  const descricao = resultado.tipo === "detalhe" ? resultado.dados.fontes?.[0]?.resumo : undefined;
  return { title: t, description: descricao || `Leia em ${SITE_NAME}`, openGraph: { title: t, url: `${SITE_URL}/noticia/${params.id}` } };
}

/**
 * NENHUM path é pré-gerado no build, de propósito.
 *
 * Antes era `[{ id: "1" }]`, o que obrigava o `next build` a consultar a API
 * para um id arbitrário. Com o tratamento de falha honesto (404 de verdade em
 * vez de artigo de demonstração), essa chamada derrubaria o build INTEIRO
 * sempre que a API não estivesse no ar — e o job `frontend-build` do CI roda
 * sem backend nenhum (`.github/workflows/ci.yml`). `[]` deixa a rota ser gerada
 * por demanda, ainda com `revalidate = 60` (ISR), tira o build da dependência
 * de dado externo e elimina a chance de conteúdo fictício ficar assado no HTML
 * estático. O build de produção roda na VPS com o Django no ar
 * (`.github/workflows/deploy.yml:302-312`).
 */
export function generateStaticParams() { return []; }
export const revalidate = 60;

export default async function Page({ params }: { params: { id: string } }) {
  const resultado = await getDetalhe(params.id);
  if (resultado.tipo === "inexistente") notFound();
  if (resultado.tipo === "indisponivel") {
    return <NoticiaIndisponivel requestId={resultado.requestId} mensagem={resultado.mensagem} />;
  }
  const d = resultado.dados;
  const jsonLd = newsArticleJsonLd({ id: d.id, tipo: d.tipo, titulo: d.titulo, categoria: d.categoria, timestamp: d.timestamp, fontes: d.fontes.map(f=>({ nome_fonte:f.nome_fonte, url_fonte_original:f.url_fonte_original })) });
  const imagemReal = d.fontes.find((f) => f.imagem_url)?.imagem_url || "";
  const heroSrc = imagemNoticia({ imagem_url: imagemReal, categoria: d.categoria, id: d.id, titulo: d.titulo });
  let relacionados: { id: number; titulo: string; categoria: string; imagem_url?: string }[] = [];
  try {
    const r = await obterFeed({ categoria: d.categoria });
    relacionados = (r.results || []).filter(x=>x.id!==d.id).slice(0, 6).map(x=>({ id: x.id, titulo: x.titulo, categoria: x.categoria || d.categoria, imagem_url: x.imagem_url }));
  } catch { /* relacionados são opcionais; a notícia continua válida */ }
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <NoticiaReporter entryTipo={d.tipo === "cluster" ? "cluster" : "item"} entryId={d.id} categoria={d.categoria} />
      <LeituraPremium detalhe={d} relacionados={relacionados} heroSrc={heroSrc} imagemReal={imagemReal} />
      <div className="mx-auto mt-6 max-w-3xl px-4">
        <CoberturaCompleta tipo={d.tipo === "cluster" ? "cluster" : "item"} id={d.id} />
        <div className="mt-6 flex flex-wrap gap-2">
          <Button asChild variant="outline" className="min-h-[44px] border-[var(--cor-borda)]"><Link href="/">Voltar ao início</Link></Button>
          <Button asChild variant="outline" className="min-h-[44px] border-[var(--cor-borda)]"><Link href="/arquivo">Ver arquivo</Link></Button>
        </div>
      </div>
    </>
  );
}
