import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { SITE_NAME } from "@/lib/site";
import { AdsSlot } from "@/components/AdsSlot";
import { obterFeed, type FeedEntrada } from "@/lib/api";
export const metadata: Metadata = { title: `Buscar — ${SITE_NAME}`, description: `Busca no ${SITE_NAME}.` };
export const revalidate = 0;
const MOCK: FeedEntrada[] = [{ tipo: "item", id: 201, titulo: "Resultados — busque por política, economia...", resumo: "Conteúdo de exemplo.", categoria: "geral", urgente: false, numero_fontes: 1, timestamp: new Date().toISOString() }];
function BuscarForm({ q }: { q: string }) {
  return (
    <form action="/buscar" className="flex gap-2">
      <Input name="q" defaultValue={q} placeholder="Buscar notícias…" aria-label="Buscar" className="h-10 bg-[var(--cor-fundo-card)]" />
      <Button type="submit" className="h-10 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]">Buscar</Button>
    </form>
  );
}
export default async function Page({ searchParams }: { searchParams: { q?: string } }) {
  const q = (searchParams.q || "").trim();
  let itens: FeedEntrada[] = [];
  if (q) {
    try { const r = await obterFeed({ busca: q }); itens = r.results || []; } catch { itens = MOCK.filter(x=> x.titulo.toLowerCase().includes(q.toLowerCase()) || !q) ; if(!itens.length) itens=MOCK; }
  }
  return (
    <div className="space-y-4">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4"><div className="hud-line mb-3" aria-hidden /><h1 className="text-xl font-bold text-[var(--cor-texto)]">Buscar</h1><p className="text-sm text-[var(--cor-texto-suave)]">Query <code className="rounded bg-[var(--cor-borda)] px-1">?q=</code> • usa <code className="rounded bg-[var(--cor-borda)] px-1">lib/intent.ts</code> no client quando houver personalização.</p><div className="mt-3"><BuscarForm q={q} /></div></div>
      {!q && <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]"><CardContent className="p-4 text-sm text-[var(--cor-texto-suave)]">Digite um termo acima. Ex.: <Link href="/buscar?q=política" className="text-[var(--cor-primaria)] hover:underline">política</Link>, <Link href="/buscar?q=tecnologia" className="text-[var(--cor-primaria)] hover:underline">tecnologia</Link>.</CardContent></Card>}
      {q && (
        <div className="space-y-3">
          <p className="text-sm text-[var(--cor-texto-suave)]">{itens.length} resultado(s) para <span className="font-semibold text-[var(--cor-texto)]">“{q}”</span></p>
          {itens.length===0 ? (
            <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]"><CardContent className="p-6 text-center text-sm text-[var(--cor-texto-suave)]">Nenhum resultado para “{q}”. <Link href="/arquivo" className="font-medium text-[var(--cor-primaria)] underline">Ver arquivo</Link> • <Link href="/" className="font-medium text-[var(--cor-primaria)] underline">Voltar ao início</Link></CardContent></Card>
          ) : (
            <div className="grid gap-3">
              {itens.map((n)=>(
                <Card key={`${n.tipo}-${n.id}`} className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-4"><div className="mb-1 flex gap-2"><Badge variant="outline" className="border-[var(--cor-borda)] capitalize">{n.categoria}</Badge><span className="text-xs text-[var(--cor-texto-suave)]">{n.numero_fontes} fontes</span></div><Link href={`/noticia/${n.id}`} className="font-bold text-[var(--cor-texto)] hover:text-[var(--cor-primaria)]">{n.titulo}</Link><p className="mt-1 text-sm text-[var(--cor-texto-suave)]">{n.resumo}</p></CardContent></Card>
              ))}
            </div>
          )}
          <AdsSlot id="buscar-infeed" formato="in-feed" className="my-6" />
          {itens.length > 6 && <AdsSlot id="buscar-horizontal" formato="horizontal" />}
        </div>
      )}
    </div>
  );
}
