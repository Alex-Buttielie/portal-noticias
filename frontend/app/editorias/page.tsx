import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SITE_NAME } from "@/lib/site";
import { CATEGORIAS, hrefSubcategoria } from "@/lib/categorias";
export const metadata: Metadata = { title: `Editorias — ${SITE_NAME}`, description: `Todas as editorias do ${SITE_NAME}.` };
export default function Page() {
  return (
    <div className="space-y-6">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-5 md:p-6"><div className="hud-line mb-3" aria-hidden /><h1 className="text-2xl font-bold tracking-tight text-[var(--cor-texto)] md:text-3xl">Editorias</h1><p className="mt-1 text-sm text-[var(--cor-texto-suave)]">Navegue por assunto — escolha a editoria ou entre direto num tema.</p></div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {CATEGORIAS.map((e)=>(
          <Card key={e.slug} className="bento bento-hover flex flex-col border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="flex flex-1 flex-col p-5"><Badge variant="outline" className="w-fit border-[var(--cor-borda)] capitalize">{e.slug}</Badge><Link href={`/categoria/${encodeURIComponent(e.slug)}`} className="mt-2 block font-bold capitalize text-[var(--cor-texto)] hover:text-[var(--cor-primaria)]">{e.nome}</Link><p className="mt-1 text-sm text-[var(--cor-texto-suave)]">{e.descricao}</p><div className="mt-3 flex flex-wrap gap-1.5">{e.subcategorias.slice(0,4).map((s)=>(<Link key={s.termo} href={hrefSubcategoria(s)} className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2.5 py-1 text-xs text-[var(--cor-texto)] hover:border-[var(--cor-primaria)] hover:text-[var(--cor-primaria)]">{s.nome}</Link>))}</div><Link href={`/categoria/${encodeURIComponent(e.slug)}`} className="mt-3 inline-flex pt-1 text-xs font-medium text-[var(--cor-primaria)] hover:underline">Ver editoria →</Link></CardContent></Card>
        ))}
      </div>
    </div>
  );
}
