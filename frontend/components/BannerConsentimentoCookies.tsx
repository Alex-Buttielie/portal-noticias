"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Cookie, ShieldCheck, Activity } from "lucide-react";
import { consentimentoRespondido, aceitarTodos, recusarNaoEssenciais, definirEscolhas, obterConsentimento, type EscolhasCookies } from "@/lib/cookie-consent";
import { useAuth } from "@/lib/auth-context";
import { sincronizarComBackendSeAutenticado } from "@/lib/cookie-consent";

const ESCOLHAS_INICIAIS: EscolhasCookies = { analytics: false, personalizacao: false, tecnico: false };

export function BannerConsentimentoCookies() {
  const [visivel, setVisivel] = useState(false);
  const [prefOpen, setPrefOpen] = useState(false);
  const [escolhas, setEscolhas] = useState<EscolhasCookies>(ESCOLHAS_INICIAIS);
  const { token } = useAuth();
  useEffect(() => { setVisivel(!consentimentoRespondido()); }, []);
  function fechar() { setVisivel(false); }
  function abrirPreferencias() {
    const atual = obterConsentimento();
    setEscolhas(atual ? { ...atual.escolhas } : ESCOLHAS_INICIAIS);
    setPrefOpen(true);
  }
  if (!visivel) return null;
  return (
    <>
      <div role="dialog" aria-label="Consentimento de cookies" aria-modal="true" className="fixed inset-x-0 bottom-0 z-[var(--z-cookies)] border-t border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-2 md:bottom-4 md:left-1/2 md:w-[min(640px,calc(100%-2rem))] md:-translate-x-1/2 md:rounded-lg md:border">
        <p className="text-sm leading-relaxed text-[var(--cor-texto)]">
          Usamos cookies essenciais e, com seu consentimento, três categorias opcionais:{" "}
          <strong>analytics</strong> (medir uso), <strong>personalização</strong> (feed recommendations e publicidade de terceiros, como AdSense) e{" "}
          <strong>diagnóstico técnico</strong> (erros e desempenho do portal, para a equipe conseguir corrigir falhas). Cada uma é escolhida separadamente em{" "}
          <Link href="/privacidade/preferencias-cookies" className="underline decoration-[var(--cor-borda)] underline-offset-2 hover:text-[var(--cor-primaria)]">preferências de cookies</Link>, e o diagnóstico técnico{" "}
          <strong>também</strong> sai se você recusar as categorias de produto. Veja a{" "}
          <Link href="/privacidade/cookies" className="underline decoration-[var(--cor-borda)] underline-offset-2 hover:text-[var(--cor-primaria)]">política de cookies</Link>.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" onClick={() => { aceitarTodos(); void sincronizarComBackendSeAutenticado(token); fechar(); }} className="inline-flex min-h-[44px] items-center rounded-md bg-[var(--cor-primaria)] px-4 text-sm font-medium text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]">Aceitar todos</button>
          <button type="button" onClick={() => { recusarNaoEssenciais(); void sincronizarComBackendSeAutenticado(token); fechar(); }} className="inline-flex min-h-[44px] items-center rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-4 text-sm font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-borda)]">Rejeitar não essenciais</button>
          <button type="button" onClick={abrirPreferencias} className="inline-flex min-h-[44px] items-center rounded-md border border-transparent px-4 text-sm font-medium text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)]">Personalizar</button>
        </div>
      </div>
      <Dialog open={prefOpen} onOpenChange={setPrefOpen}>
        <DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Cookie className="h-5 w-5 text-[var(--cor-primaria)]" /> Preferências de cookies</DialogTitle>
            <DialogDescription>Escolha quais categorias podemos usar. Você pode mudar isso a qualquer momento.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
              <div className="space-y-0.5"><Label className="text-sm font-medium">Essenciais</Label><p className="text-xs text-[var(--cor-texto-suave)]">Necessários para o site funcionar. Sempre ativos.</p></div>
              <span className="inline-flex items-center gap-1 rounded-full bg-[var(--cor-sucesso-suave)] px-2 py-1 text-xs font-medium text-[var(--cor-sucesso)]"><ShieldCheck className="h-3 w-3" /> Ativo</span>
            </div>
            <div className="flex items-center justify-between rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
              <div className="space-y-0.5"><Label htmlFor="cc-analytics">Analytics</Label><p className="text-xs text-[var(--cor-texto-suave)]">Mede audiência e uso: páginas vistas, cliques e buscas. Não identifica você.</p></div>
              <Switch id="cc-analytics" checked={escolhas.analytics} onCheckedChange={(v) => setEscolhas((e) => ({ ...e, analytics: v }))} />
            </div>
            <div className="flex items-center justify-between rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
              <div className="space-y-0.5"><Label htmlFor="cc-pers">Personalização</Label><p className="text-xs text-[var(--cor-texto-suave)]">Recomendações, feed personalizado e publicidade de terceiros, como AdSense.</p></div>
              <Switch id="cc-pers" checked={escolhas.personalizacao} onCheckedChange={(v) => setEscolhas((e) => ({ ...e, personalizacao: v }))} />
            </div>
            <div className="flex items-center justify-between rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
              <div className="space-y-0.5">
                <Label htmlFor="cc-tecnico" className="flex items-center gap-1.5"><Activity className="h-3.5 w-3.5" aria-hidden />Diagnóstico técnico</Label>
                <p className="text-xs text-[var(--cor-texto-suave)]">Envia erros e medidas de desempenho para a equipe encontrar e corrigir falhas. É separado de analytics: não mede audiência nem o que você lê, e nunca inclui token, e-mail ou o conteúdo das páginas.</p>
              </div>
              <Switch id="cc-tecnico" checked={escolhas.tecnico} onCheckedChange={(v) => setEscolhas((e) => ({ ...e, tecnico: v }))} />
            </div>
            <p className="text-xs text-[var(--cor-texto-suave)]">Preferências completas em <Link href="/privacidade/preferencias-cookies" onClick={()=>setPrefOpen(false)} className="text-[var(--cor-primaria)] underline">/privacidade/preferencias-cookies</Link>.</p>
          </div>
          <DialogFooter className="flex-col gap-2 sm:flex-col">
            <Button onClick={() => { definirEscolhas(escolhas); void sincronizarComBackendSeAutenticado(token); setPrefOpen(false); fechar(); }} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">Salvar escolhas</Button>
            <Button variant="outline" onClick={() => setPrefOpen(false)} className="w-full min-h-[44px]">Fechar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
