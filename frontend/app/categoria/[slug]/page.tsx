import { Fragment } from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SITE_NAME, SITE_URL } from "@/lib/site";
import { obterFeed, type FeedEntrada } from "@/lib/api";
import { ImagemNoticia } from "@/components/ImagemNoticia";
import { AdsSlot } from "@/components/AdsSlot";
import { hrefSubcategoria, subcategoriasCompletas } from "@/lib/categorias";
import { CategoriaReporter } from "@/components/Reporters";
import { breadcrumbListJsonLd } from "@/lib/schema";
// P0-08: estado vazio real quando a categoria não tem itens — em vez de
// popular a tela com notícias fictícias.
import { EstadoVazio } from "@/components/EstadoVazio";
// P0-10: renderiza o JSON-LD com escape de contexto `<script>`.
import { JsonLd } from "@/components/JsonLd";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug: slugParam } = await params;
  const cat = decodeURIComponent(slugParam);
  return { title: `${cat} — ${SITE_NAME}`, description: `Notícias de ${cat} no ${SITE_NAME}.`, openGraph: { title: `${cat} — ${SITE_NAME}`, url: `${SITE_URL}/categoria/${encodeURIComponent(cat)}` } };
}
export function generateStaticParams() { return [{ slug: "politica" }, { slug: "economia" }, { slug: "tecnologia" }, { slug: "esportes" }, { slug: "cultura" }]; }
export const revalidate = 60;
function timeAgo(iso: string){const d=Date.now()-new Date(iso).getTime();const h=Math.floor(d/3600000);if(h<1)return"agora";if(h<24)return`${h}h`;return`${Math.floor(h/24)}d`;}
export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug: slugParam } = await params;
  const slug = decodeURIComponent(slugParam);
  // P0-08: sem fallback de conteúdo. Feed vazio ou API fora => estado vazio.
  const r = await obterFeed({ categoria: slug }).catch(() => null);
  const itens: FeedEntrada[] = r?.results ?? [];
  const erro = !r;
  const jsonLd = breadcrumbListJsonLd([{ nome: "Início", url: SITE_URL }, { nome: slug, url: `${SITE_URL}/categoria/${encodeURIComponent(slug)}` }]);
  const subs = subcategoriasCompletas(slug, itens);
  return (
    <div className="space-y-6">
      <CategoriaReporter categoria={slug} />
      <JsonLd dados={jsonLd} />
      <div className="flex items-center gap-2 text-xs text-[var(--cor-texto-suave)]"><Link href="/" className="hover:underline">Início</Link><span aria-hidden>›</span><Link href="/editorias" className="hover:underline">Editorias</Link><span aria-hidden>›</span><span className="capitalize text-[var(--cor-texto)]">{slug}</span></div>
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-5 md:p-6">
        <div className="hud-line mb-3" aria-hidden />
        <h1 className="text-2xl font-bold capitalize tracking-tight text-[var(--cor-texto)] md:text-3xl">{slug}</h1>
        <p className="mt-1 text-sm text-[var(--cor-texto-suave)]">{itens.length} manchetes</p>
        {subs.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-1.5" aria-label={`Temas em ${slug}`}>
            {subs.map((s)=>(
              <Link key={s.termo} href={hrefSubcategoria(s)} className="inline-flex items-center gap-1 rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-1.5 text-xs font-medium text-[var(--cor-texto)] hover:border-[var(--cor-primaria)] hover:text-[var(--cor-primaria)]">
                {s.nome}
                {"viva" in s && s.viva && <span className="h-1.5 w-1.5 rounded-full bg-[var(--cor-sinal)] motion-safe:animate-pulse" aria-label="Em alta nas notícias" />}
              </Link>
            ))}
          </div>
        )}
      </div>
      <AdsSlot id="categoria-topo" formato="horizontal" />
      <div className="grid gap-4 md:grid-cols-2">
        {itens.length ? itens.map((n,i)=>(
          <Fragment key={`${n.tipo}-${n.id}`}>
          <Card className="bento bento-hover overflow-hidden border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <div className="aspect-[16/9] overflow-hidden bg-[var(--cor-fundo-elevado)]">
              <ImagemNoticia src={n.imagem_url} seed={`${n.categoria || "geral"}-${n.id}`} alt={n.titulo} className="h-full w-full object-cover" />
            </div>
            <CardContent className="p-4"><div className="mb-2 flex gap-2"><Badge variant="outline" className="border-[var(--cor-borda)] capitalize">{n.categoria}</Badge>{n.urgente&&<Badge className="bg-[var(--cor-sinal)] text-[var(--cor-texto-invertido)]">urgente</Badge>}<span className="ml-auto text-xs text-[var(--cor-texto-suave)]">{timeAgo(n.timestamp)}</span></div><Link href={`/noticia/${n.id}`} className="line-clamp-2 font-bold text-[var(--cor-texto)] hover:text-[var(--cor-primaria)]">{n.titulo}</Link><p className="mt-1 line-clamp-2 text-sm text-[var(--cor-texto-suave)]">{n.resumo}</p></CardContent></Card>
          {(i+1)%6===0 && <AdsSlot id={`categoria-infeed-${Math.floor(i/6)}`} formato="in-feed" className="md:col-span-2" />}
          </Fragment>
        )) : <EstadoVazio
          className="md:col-span-2"
          tom={erro ? "erro" : "neutro"}
          titulo={erro ? "Não foi possível carregar as notícias desta editoria" : "Nenhuma notícia disponível agora"}
          descricao={erro ? "O serviço de notícias não respondeu. Nenhuma manchete foi fabricada para preencher a página." : `Ainda não há manchetes publicadas em ${slug}.`}
          acao={{ rotulo: "Ver arquivo completo", href: "/arquivo" }}
        />}
      </div>
      {itens.length>0 && itens.length%6!==0 && <AdsSlot id="categoria-infeed-final" formato="in-feed" />}
      {itens.length < 18 && <AdsSlot id="categoria-pos" formato="horizontal" className="my-6" />}
    </div>
  );
}
