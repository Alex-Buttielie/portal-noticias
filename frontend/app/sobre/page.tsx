import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { SITE_NAME, SITE_DESCRIPTION } from "@/lib/site";
export const metadata: Metadata = { title: `Sobre — ${SITE_NAME}`, description: SITE_DESCRIPTION };
export default function Page() {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-6">
        <div className="hud-line mb-4" aria-hidden />
        <h1 className="text-3xl font-bold tracking-tight text-[var(--cor-texto)]">Sobre</h1>
        <p className="mt-2 text-pretty leading-relaxed text-[var(--cor-texto-suave)]">{SITE_DESCRIPTION} Agregação com rastreabilidade de origem — cada manchete cita suas fontes.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-4"><p className="text-xs tracking-widest text-[var(--cor-texto-suave)]">LEITURA CONFORTÁVEL</p><p className="mt-1 text-sm text-[var(--cor-texto)]">Cores suaves para leitura prolongada, com destaque para o que importa.</p></CardContent></Card>
        <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]"><CardContent className="p-4"><p className="text-xs tracking-widest text-[var(--cor-texto-suave)]">EM DESTAQUE</p><p className="mt-1 text-sm text-[var(--cor-texto)]">Seleção do dia em destaque, resto organizado para você.</p></CardContent></Card>
        <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-4"><p className="text-xs tracking-widest text-[var(--cor-texto-suave)]">RASTREABILIDADE</p><p className="mt-1 text-sm text-[var(--cor-texto)]">Toda notícia exibe fontes com link original. <Link href="/arquivo" className="text-[var(--cor-primaria)] hover:underline">Arquivo</Link> • <Link href="/privacidade" className="text-[var(--cor-primaria)] hover:underline">Privacidade</Link></p></CardContent></Card>
      </div>
    </div>
  );
}
