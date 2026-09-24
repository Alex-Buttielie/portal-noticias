import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SITE_NAME } from "@/lib/site";
import { obterFeed, type FeedEntrada } from "@/lib/api";
import { formatarDataHoraCompacta } from "@/lib/datas";
import { AdsSlot } from "@/components/AdsSlot";
import { ImagemNoticia } from "@/components/ImagemNoticia";
export const metadata: Metadata = { title: `Arquivo — ${SITE_NAME}`, description: `Arquivo de notícias do ${SITE_NAME}.` };
export const revalidate = 60;
const MOCK: FeedEntrada[] = Array.from({ length: 12 }, (_, i) => ({ tipo: i % 3 === 0 ? "cluster" : "item", id: 300 + i, titulo: `Arquivo #${300 + i} — manchete demonstrativa`, resumo: "Conteúdo de exemplo para demonstração.", categoria: ["política", "economia", "tecnologia", "cidades"][i % 4], urgente: i === 0, numero_fontes: 2 + (i % 3), timestamp: new Date(Date.now() - i * 3600000 * 6).toISOString() }));
export default async function Page({ searchParams }: { searchParams: { page?: string } }) {
  const page = Math.max(1, Number(searchParams.page) || 1);
  let itens: FeedEntrada[] = [];
  try { const r = await obterFeed({ page }); itens = r.results?.length ? r.results : MOCK; } catch { itens = MOCK; }
  return (
    <div className="space-y-4">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-5"><div className="hud-line mb-3" aria-hidden /><h1 className="text-2xl font-bold text-[var(--cor-texto)]">Arquivo</h1><p className="text-sm text-[var(--cor-texto-suave)]">Página {page} — arquivo cronológico</p></div>
      <div className="grid gap-3">
        {itens.map((n)=>(
          <Link key={`${n.tipo}-${n.id}`} href={`/noticia/${n.id}`} className="flex gap-3 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3 hover:bg-[var(--cor-primaria-suave)]">
            <span className="hidden aspect-[16/9] h-14 w-24 shrink-0 overflow-hidden rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] md:block" aria-hidden>
              <ImagemNoticia src={n.imagem_url} seed={`${n.categoria || "geral"}-${n.id}`} alt="" sizes="192px" className="h-full w-full object-cover" />
            </span>
            <div className="min-w-0 flex-1"><div className="flex items-center gap-2"><Badge variant="outline" className="border-[var(--cor-borda)] capitalize text-xs">{n.categoria}</Badge>{n.urgente&&<Badge className="bg-[var(--cor-sinal)] text-[var(--cor-texto-invertido)] text-xs">urgente</Badge>}<span className="ml-auto text-xs text-[var(--cor-texto-suave)]">{formatarDataHoraCompacta(n.timestamp)}</span></div><p className="mt-1 line-clamp-2 font-semibold text-[var(--cor-texto)]">{n.titulo}</p><p className="line-clamp-1 text-sm text-[var(--cor-texto-suave)]">{n.resumo}</p></div>
          </Link>
        ))}
      </div>
      <AdsSlot id="arquivo-infeed" formato="in-feed" />
      {itens.length > 6 && <AdsSlot id="arquivo-horizontal" formato="horizontal" className="my-6" />}
      <div className="flex gap-2">
        {page > 1 && <Link href={`/arquivo?page=${page - 1}`} className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 py-2 text-sm text-[var(--cor-texto)] hover:bg-[var(--cor-borda)]">← Anterior</Link>}
        <Link href={`/arquivo?page=${page + 1}`} className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 py-2 text-sm text-[var(--cor-texto)] hover:bg-[var(--cor-borda)]">Próxima →</Link>
      </div>
    </div>
  );
}
