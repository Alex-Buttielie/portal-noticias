import type { Metadata } from "next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SITE_NAME } from "@/lib/site";
export const metadata: Metadata = { title: `Empresa - ${SITE_NAME}` };
export default function Page(){
  return (<div className="mx-auto max-w-3xl space-y-4 py-6"><div className="hud-line" aria-hidden /><div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-6"><h1 className="text-2xl font-bold text-[var(--cor-texto)]">B2B Corporativo</h1><p className="text-sm text-[var(--cor-texto-suave)]">Monitoramento por critérios</p></div><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle className="flex items-center gap-2">Painel <Badge className="bg-[var(--cor-neon-violeta)] text-[var(--cor-texto-invertido)]">B2B</Badge></CardTitle></CardHeader><CardContent><p className="text-sm text-[var(--cor-texto-suave)]">Faça login para acessar critérios, itens monitorados, resumo executivo e membros.</p></CardContent></Card></div>);
}
