"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { CheckCircle2, Sparkles } from "lucide-react";
import { obterTodasLeituras } from "@/lib/intent";
import { categoriasPorAfinidade } from "@/lib/personalizar";
import { useAuth } from "@/lib/auth-context";
export default function Page(){
  const { usuario } = useAuth(); const router=useRouter();
  const [cats,setCats]=useState<string[]>([]);
  const [leituras,setLeituras]=useState<Record<string,number>>({});
  const [savedOpen,setSavedOpen]=useState(false);
  useEffect(()=>{ setLeituras(obterTodasLeituras()); setCats(categoriasPorAfinidade({interesses: usuario?.interesses || []})); },[usuario]);
  function limpar(){ try{ localStorage.removeItem("portal_noticias_intent"); }catch{} setLeituras({}); setCats(categoriasPorAfinidade({interesses: usuario?.interesses || []})); setSavedOpen(true); }
  const totalLeituras=Object.values(leituras).reduce((a,b)=>a+b,0);
  const passo = cats.length ? 2 : totalLeituras ? 1 : 0;
  const pct = passo===0 ? 33 : passo===1 ? 66 : 100;
  return (<div className="mx-auto max-w-2xl space-y-4 py-6"><div className="hud-line" aria-hidden />
    <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4">
      <p className="text-xs font-medium text-[var(--cor-texto-suave)]">Passo {Math.min(passo+1,3)} de 3</p>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--cor-borda)]"><div className="h-full bg-[var(--cor-primaria)] transition-all" style={{ width: `${pct}%` }} /></div>
      <div className="mt-2 flex gap-2 text-xs"><span className={pct>=33?"font-bold text-[var(--cor-primaria)]":"text-[var(--cor-texto-suave)]"}>1 Ler</span><span className={pct>=66?"font-bold text-[var(--cor-primaria)]":"text-[var(--cor-texto-suave)]"}>2 Escolher</span><span className={pct>=100?"font-bold text-[var(--cor-primaria)]":"text-[var(--cor-texto-suave)]"}>3 Feed</span></div>
    </div>
    <Dialog open={savedOpen} onOpenChange={setSavedOpen}>
      <DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <DialogHeader className="items-center text-center sm:items-center sm:text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--cor-sucesso-suave)] text-[var(--cor-sucesso)]"><CheckCircle2 className="h-6 w-6" /></div>
          <DialogTitle className="text-center">Preferências salvas!</DialogTitle>
          <DialogDescription className="text-center">Seu feed foi atualizado com suas escolhas.</DialogDescription>
        </DialogHeader>
        <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 text-sm text-[var(--cor-texto-suave)] flex items-center gap-2"><Sparkles className="h-4 w-4 text-[var(--cor-primaria)]" /> As próximas notícias vão refletir suas preferências.</div>
        <DialogFooter className="flex-col gap-2 sm:flex-col">
          <Button onClick={()=>{ setSavedOpen(false); router.push("/"); }} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">Ver meu feed personalizado</Button>
          <Button variant="outline" onClick={()=>setSavedOpen(false)} className="w-full min-h-[44px]">Continuar aqui</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Personalizar</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Ajuste o que você quer ver primeiro</CardDescription></CardHeader><CardContent className="space-y-4">
      <div><p className="text-sm font-medium text-[var(--cor-texto)]">Afinidade</p>{cats.length? <div className="mt-2 flex flex-wrap gap-2">{cats.map((c)=> (<Badge key={c} className="bg-[var(--cor-neon-ciano)] text-[var(--cor-texto-invertido)] capitalize">{c}</Badge>))}</div> : <p className="text-sm text-[var(--cor-texto-suave)]">Sem sinal ainda — leia notícias para personalizar. <Link href="/" className="text-[var(--cor-primaria)] underline">Ir para o feed</Link></p>}</div>
      <div><p className="text-sm font-medium text-[var(--cor-texto)]">Leituras por categoria</p>{Object.keys(leituras).length? <div className="mt-2 grid grid-cols-2 gap-2">{Object.entries(leituras).map(([k,v])=> (<div key={k} className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-2"><p className="text-xs capitalize text-[var(--cor-texto-suave)]">{k}</p><p className="font-bold text-[var(--cor-texto)]">{v}</p></div>))}</div> : <p className="text-sm text-[var(--cor-texto-suave)]">Nenhuma leitura registrada. <Link href="/arquivo" className="text-[var(--cor-primaria)] underline">Explorar arquivo</Link></p>}</div>
      <div className="flex flex-wrap gap-2">
        <Button onClick={()=>setSavedOpen(true)} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">Salvar preferências</Button>
        <Button variant="outline" onClick={limpar} className="min-h-[44px]">Limpar sinais</Button>
        <Button asChild className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]"><Link href="/">Ver meu feed personalizado</Link></Button>
      </div>
    </CardContent></Card></div>);
}
