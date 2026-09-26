import type { Metadata } from "next";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { SITE_NAME } from "@/lib/site";
import ListaEsperaForm from "./ListaEsperaForm";
export const metadata: Metadata = { title: `Lista de espera - ${SITE_NAME}` };
export default function Page(){
  return (<div className="mx-auto max-w-xl space-y-4 py-6"><div className="hud-line" aria-hidden /><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Lista de espera</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Avisamos quando liberarmos o acesso.</CardDescription></CardHeader><CardContent><ListaEsperaForm /></CardContent></Card></div>);
}
