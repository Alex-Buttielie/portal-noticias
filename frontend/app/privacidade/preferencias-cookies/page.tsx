"use client";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { obterConsentimento, definirEscolhas } from "@/lib/cookie-consent";
export default function Page(){
  const [analytics,setAnalytics]=useState(false); const [personalizacao,setPersonalizacao]=useState(false);
  useEffect(()=>{ const c=obterConsentimento(); if(c){ setAnalytics(!!c.escolhas.analytics); setPersonalizacao(!!c.escolhas.personalizacao); } },[]);
  const salvar=()=>{ definirEscolhas({analytics, personalizacao}); alert("Preferencias salvas."); };
  return (<div className="mx-auto max-w-xl space-y-4 py-6"><div className="hud-line" aria-hidden /><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Preferencias de cookies</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Gerencie seu consentimento - LGPD</CardDescription></CardHeader><CardContent className="space-y-4">
    <div className="flex items-center justify-between rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><Label htmlFor="an">Analytics</Label><Switch id="an" checked={analytics} onCheckedChange={setAnalytics} /></div>
    <div className="flex items-center justify-between rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><Label htmlFor="pe">Personalizacao</Label><Switch id="pe" checked={personalizacao} onCheckedChange={setPersonalizacao} /></div>
    <Button onClick={salvar} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">Salvar</Button>
  </CardContent></Card></div>);
}
