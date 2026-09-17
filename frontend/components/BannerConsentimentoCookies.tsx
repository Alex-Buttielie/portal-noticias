"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { consentimentoRespondido, aceitarTodos, recusarNaoEssenciais, definirEscolhas } from "@/lib/cookie-consent";
import { useAuth } from "@/lib/auth-context";
import { sincronizarComBackendSeAutenticado } from "@/lib/cookie-consent";
export function BannerConsentimentoCookies() {
  const [visivel, setVisivel] = useState(false);
  const [personalizar, setPersonalizar] = useState(false);
  const [analytics, setAnalytics] = useState(false);
  const [personalizacao, setPersonalizacao] = useState(false);
  const { token } = useAuth();
  useEffect(() => { setVisivel(!consentimentoRespondido()); }, []);
  function fechar() { setVisivel(false); }
  if (!visivel) return null;
  return (
    <div role="dialog" aria-label="Consentimento de cookies" aria-modal="true" className="fixed inset-x-0 bottom-0 z-[var(--z-cookies)] border-t border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-2 md:bottom-4 md:left-1/2 md:w-[min(640px,calc(100%-2rem))] md:-translate-x-1/2 md:rounded-lg md:border">
      {!personalizar ? (
        <>
          <p className="text-sm leading-relaxed text-[var(--cor-texto)]">Usamos cookies essenciais e, com seu consentimento, cookies de analytics e personalização. Veja nossa <Link href="/privacidade/cookies" className="underline decoration-[var(--cor-borda)] underline-offset-2 hover:text-[var(--cor-primaria)]">política de cookies</Link>.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" onClick={() => { aceitarTodos(); void sincronizarComBackendSeAutenticado(token); fechar(); }} className="inline-flex min-h-[44px] items-center rounded-md bg-[var(--cor-primaria)] px-4 text-sm font-medium text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]">Aceitar todos</button>
            <button type="button" onClick={() => { recusarNaoEssenciais(); void sincronizarComBackendSeAutenticado(token); fechar(); }} className="inline-flex min-h-[44px] items-center rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-4 text-sm font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-borda)]">Rejeitar não essenciais</button>
            <button type="button" onClick={() => setPersonalizar(true)} className="inline-flex min-h-[44px] items-center rounded-md border border-transparent px-4 text-sm font-medium text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)]">Personalizar</button>
          </div>
        </>
      ) : (
        <>
          <h2 className="text-sm font-semibold text-[var(--cor-texto)]">Personalizar cookies</h2>
          <label className="mt-3 flex items-center gap-2 text-sm text-[var(--cor-texto)]"><input type="checkbox" checked disabled className="h-4 w-4 accent-[var(--cor-primaria)]" /> Essenciais (sempre ativos)</label>
          <label className="mt-2 flex items-center gap-2 text-sm text-[var(--cor-texto)]"><input type="checkbox" checked={analytics} onChange={(e) => setAnalytics(e.target.checked)} className="h-4 w-4 accent-[var(--cor-primaria)]" /> Analytics</label>
          <label className="mt-2 flex items-center gap-2 text-sm text-[var(--cor-texto)]"><input type="checkbox" checked={personalizacao} onChange={(e) => setPersonalizacao(e.target.checked)} className="h-4 w-4 accent-[var(--cor-primaria)]" /> Personalização</label>
          <div className="mt-4 flex gap-2">
            <button type="button" onClick={() => { definirEscolhas({ analytics, personalizacao }); void sincronizarComBackendSeAutenticado(token); fechar(); }} className="inline-flex min-h-[44px] items-center rounded-md bg-[var(--cor-primaria)] px-4 text-sm font-medium text-[var(--cor-texto-invertido)]">Salvar escolhas</button>
            <button type="button" onClick={() => setPersonalizar(false)} className="inline-flex min-h-[44px] items-center rounded-md border border-[var(--cor-borda)] px-4 text-sm">Voltar</button>
          </div>
        </>
      )}
    </div>
  );
}
