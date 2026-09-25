"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ShieldCheck } from "lucide-react";
import { obterConsentimento, definirEscolhas, type EscolhasCookies } from "@/lib/cookie-consent";
import { useAuth } from "@/lib/auth-context";
import { sincronizarComBackendSeAutenticado } from "@/lib/cookie-consent";

const INICIAIS: EscolhasCookies = { analytics: false, personalizacao: false, tecnico: false };

/**
 * Preferências de cookies — três categorias opcionais, cada uma com switch
 * próprio (run 20260925-1020-observabilidade, critérios 5 e 27).
 *
 * "Diagnóstico técnico" não é apelido de analytics: é o que habilita o envio de
 * eventos técnicos (erros, Web Vitals, identificador de requisição). Sem ele,
 * o portal funciona normalmente e nada técnico sai do navegador — o backend
 * também é fail-closed e descarta o que chegar sem o header.
 */
export default function Page(){
  const [escolhas,setEscolhas]=useState<EscolhasCookies>(INICIAIS);
  const [salvo,setSalvo]=useState(false);
  const { token } = useAuth();
  useEffect(()=>{ const c=obterConsentimento(); if(c) setEscolhas({...c.escolhas}); },[]);
  const salvar=()=>{ definirEscolhas(escolhas); void sincronizarComBackendSeAutenticado(token); setSalvo(true); setTimeout(()=>setSalvo(false),3000); };
  return (<div className="mx-auto max-w-xl space-y-4 py-6"><div className="hud-line" aria-hidden /><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Preferências de cookies</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Gerencie seu consentimento - LGPD</CardDescription></CardHeader><CardContent className="space-y-4">
    <div className="flex items-center justify-between rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><div className="space-y-0.5"><Label className="text-sm font-medium">Essenciais</Label><p className="text-xs text-[var(--cor-texto-suave)]">Necessários para o site funcionar. Sempre ativos.</p></div><span className="inline-flex items-center gap-1 rounded-full bg-[var(--cor-sucesso-suave)] px-2 py-1 text-xs font-medium text-[var(--cor-sucesso)]"><ShieldCheck className="h-3 w-3" aria-hidden /> Ativo</span></div>
    <div className="flex items-center justify-between rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><div className="space-y-0.5"><Label htmlFor="an">Analytics</Label><p className="text-xs text-[var(--cor-texto-suave)]">Mede audiência e uso: páginas vistas, cliques e buscas.</p></div><Switch id="an" checked={escolhas.analytics} onCheckedChange={(v)=>setEscolhas((e)=>({...e,analytics:v}))} /></div>
    <div className="flex items-center justify-between rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><div className="space-y-0.5"><Label htmlFor="pe">Personalização</Label><p className="text-xs text-[var(--cor-texto-suave)]">Recomendações, feed personalizado e publicidade de terceiros, como AdSense.</p></div><Switch id="pe" checked={escolhas.personalizacao} onCheckedChange={(v)=>setEscolhas((e)=>({...e,personalizacao:v}))} /></div>
    <div className="flex items-center justify-between rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><div className="space-y-0.5"><Label htmlFor="te">Diagnóstico técnico</Label><p className="text-xs text-[var(--cor-texto-suave)]">Envia erros e desempenho para a equipe corrigir falhas. Separado de analytics: não mede audiência, e nunca inclui token, e-mail ou o conteúdo das páginas.</p></div><Switch id="te" checked={escolhas.tecnico} onCheckedChange={(v)=>setEscolhas((e)=>({...e,tecnico:v}))} /></div>
    <p className="text-xs text-[var(--cor-texto-suave)]">
      Enquanto o diagnóstico técnico estiver desligado, o portal funciona por completo e nenhum evento de erro ou desempenho sai do seu navegador. Detalhes em{" "}
      <Link href="/privacidade/cookies" className="text-[var(--cor-primaria)] underline">política de cookies</Link> e{" "}
      <Link href="/privacidade/politica" className="text-[var(--cor-primaria)] underline">política de privacidade</Link>.
    </p>
    <Button onClick={salvar} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">Salvar</Button>
    {salvo && <p role="status" className="flex items-center gap-1 text-sm text-[var(--cor-texto)]"><Badge className="bg-[var(--cor-sucesso)] text-[var(--cor-texto-invertido)]">Salvo</Badge> Preferências atualizadas neste aparelho.</p>}
  </CardContent></Card></div>);
}
