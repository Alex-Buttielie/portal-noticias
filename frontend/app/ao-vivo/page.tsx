import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SITE_NAME } from "@/lib/site";
import { obterUrgentes, type FeedEntrada } from "@/lib/api";
import { formatarDataHoraCompacta } from "@/lib/datas";
import { EstadoVazio } from "@/components/EstadoVazio";
export const metadata: Metadata = { title: `Ao vivo — ${SITE_NAME}`, description: `Cobertura ao vivo no ${SITE_NAME} — urgentes em tempo real.` };
export const revalidate = 30;
export default async function Page() {
  // P0-08: sem item urgente inventado. Falha/vazio => estado honesto.
  const r = await obterUrgentes(12).catch(() => null);
  const itens: FeedEntrada[] = r ?? [];
  const erro = !r;
  return (
    <div className="space-y-4">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-sinal)] bg-[var(--cor-fundo-card)] p-4">
        <div className="flex items-center gap-2"><span className="h-2 w-2 animate-pulse rounded-full bg-[var(--cor-sinal)]" aria-hidden /><h1 className="text-xl font-bold tracking-tight text-[var(--cor-texto)]">Ao vivo</h1><Badge className="bg-[var(--cor-sinal)] text-[var(--cor-texto-invertido)]">LIVE</Badge><span className="ml-auto text-xs text-[var(--cor-texto-suave)]">{itens.length} urgentes</span></div>
        <div className="hud-line mt-3" aria-hidden />
        <p className="mt-2 text-sm text-[var(--cor-texto-suave)]">Atualização contínua a cada 30 segundos.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {itens.length === 0 ? (
          <EstadoVazio
            className="md:col-span-2"
            tom={erro ? "erro" : "neutro"}
            titulo={erro ? "Não foi possível carregar a cobertura ao vivo" : "Nenhuma notícia urgente agora"}
            descricao={erro ? "O serviço de notícias não respondeu. Nada foi fabricado para preencher a tela." : "No momento não há manchetes marcadas como urgentes. A cobertura aparece aqui assim que a redação publicar algo urgente."}
            acao={{ rotulo: "Ver as últimas notícias", href: "/" }}
          />
        ) : itens.map((n)=>(
          <Card key={`${n.tipo}-${n.id}`} className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-4"><div className="mb-2 flex items-center gap-2"><Badge className="bg-[var(--cor-sinal)] text-[var(--cor-texto-invertido)]">urgente</Badge><Badge variant="outline" className="border-[var(--cor-borda)] capitalize">{n.categoria}</Badge><span className="ml-auto text-xs text-[var(--cor-texto-suave)]">{formatarDataHoraCompacta(n.timestamp)} • {n.numero_fontes} fontes</span></div><Link href={`/noticia/${n.id}`} className="font-bold leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)]">{n.titulo}</Link><p className="mt-1 text-sm text-[var(--cor-texto-suave)]">{n.resumo}</p></CardContent></Card>
        ))}
      </div>
    </div>
  );
}
