import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SITE_NAME } from "@/lib/site";
export const metadata: Metadata = { title: `Editorias — ${SITE_NAME}`, description: `Todas as editorias do ${SITE_NAME}.` };
const EDS = [
  { slug: "política", desc: "Poder, eleições e bastidores." },
  { slug: "economia", desc: "Mercados, negócios e finanças." },
  { slug: "tecnologia", desc: "Inovação, IA e produto." },
  { slug: "esportes", desc: "Jogos, clubes e bastidores." },
  { slug: "cultura", desc: "Arte, música e cena." },
  { slug: "saúde", desc: "Ciência, bem-estar e SUS." },
  { slug: "mundo", desc: "Geopolítica e correspondentes." },
  { slug: "cidades", desc: "Mobilidade, clima e serviço." },
];
export default function Page() {
  return (
    <div className="space-y-4">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-5"><div className="hud-line mb-3" aria-hidden /><h1 className="text-2xl font-bold tracking-tight text-[var(--cor-texto)]">Editorias</h1><p className="text-sm text-[var(--cor-texto-suave)]">Navegue por assunto.</p></div>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        {EDS.map((e)=>(
          <Card key={e.slug} className="bento bento-hover border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-4"><Badge variant="outline" className="border-[var(--cor-borda)] capitalize">{e.slug}</Badge><Link href={`/categoria/${encodeURIComponent(e.slug)}`} className="mt-2 block font-bold capitalize text-[var(--cor-texto)] hover:text-[var(--cor-primaria)]">{e.slug}</Link><p className="mt-1 text-sm text-[var(--cor-texto-suave)]">{e.desc}</p><Link href={`/categoria/${encodeURIComponent(e.slug)}`} className="mt-3 inline-flex text-xs font-medium text-[var(--cor-primaria)] hover:underline">Ver editoria →</Link></CardContent></Card>
        ))}
      </div>
    </div>
  );
}
