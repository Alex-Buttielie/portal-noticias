"use client";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";
const CARDS = [
  { href: "/admin/usuarios", k: "USUÁRIOS", t: "Papéis e status", d: "Busca, filtro por papel, promover/rebaixar, ativar/desativar" },
  { href: "/admin/fila", k: "FILA", t: "Curadoria", d: "Pendentes, aprovar/rejeitar, urgente, cluster" },
  { href: "/admin/planos", k: "PLANOS", t: "Assinatura", d: "Criar, editar preço/duração, ativar/desativar, exclusão protegida" },
  { href: "/admin/limites", k: "LIMITES", t: "Gating", d: "FeatureLimit por chave/plano, valor e descrição, log de alteração" },
  { href: "/admin/assinaturas", k: "ASSINATURAS", t: "Receita", d: "Filtro por status/plano/busca, detalhe e pagamentos" },
  { href: "/admin/moderacao", k: "MODERAÇÃO", t: "Denúncias", d: "Lista por status, ação e resolução" },
  { href: "/admin/metricas", k: "MÉTRICAS", t: "Negócio", d: "Painel por período, séries, distribuições, funil" },
  { href: "/admin/robos", k: "ROBÔS", t: "Ingestão", d: "Fontes, configuração, execuções e disparo manual — controle total" },
];
export default function Page(){
  const { usuario, token, carregando } = useAuth(); const r=useRouter();
  useEffect(()=>{ if(!carregando && !token) r.replace("/login"); },[carregando,token,r]);
  if(carregando) return <div className="h-24 animate-pulse bg-[var(--cor-skeleton-base)] rounded-[var(--raio-lg)]" />;
  if(usuario && usuario.papel!=="admin") return (<div className="mx-auto max-w-xl py-8"><Card className="bento border-[var(--cor-erro)] bg-[var(--cor-erro-suave)]"><CardContent className="p-6 text-center"><p className="text-sm text-[var(--cor-erro)]">Acesso restrito a admin.</p><Link href="/" className="text-sm text-[var(--cor-primaria)] underline">Voltar</Link></CardContent></Card></div>);
  return (<div className="space-y-4 py-2"><div className="hud-line" aria-hidden /><Card className="bento"><CardHeader><CardTitle>Painel de controle</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Central do sistema — todas as operações de administração. Robôs com controle total em /admin/robos.</CardDescription></CardHeader><CardContent><div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">{CARDS.map((c)=>(<Link key={c.href} href={c.href} className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-4 hover:bg-[var(--cor-primaria-suave)] transition-colors"><p className="text-xs tracking-widest text-[var(--cor-texto-suave)]">{c.k}</p><p className="font-bold text-[var(--cor-texto)]">{c.t}</p><p className="mt-1 text-xs text-[var(--cor-texto-suave)]">{c.d}</p></Link>))}</div><div className="mt-4 flex flex-wrap gap-2"><Badge variant="outline" className="border-[var(--cor-borda)]">{usuario?.email||"admin"}</Badge><Badge className="bg-[var(--cor-neon-violeta)] text-[var(--cor-texto-invertido)]">admin</Badge><Badge variant="outline" className="border-[var(--cor-borda)]">8 módulos</Badge></div></CardContent></Card></div>);
}
