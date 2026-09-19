"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import BuscaCep from "@/components/BuscaCep";
import { obterRegiaoPorGeolocation, type Regiao } from "@/lib/regiao";
import { Locate, MapPin, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Consentimento de localização (FRENTE 2) — padrão usado em "Perto de você"
// (Home). O Radar segue o mesmo padrão via `RadarLocalSimples` (perguntar
// antes de detectar, explicar o benefício, manual por cidade/CEP, alterar e
// limpar depois, exibição minimalista cidade/UF, nunca presume local).
// Aqui: pergunta, explica o benefício, permite recusar ("Agora não"),
// escolher manualmente (CEP) e alterar depois. Sem consentimento, nada é
// detectado nem exibido.
// ---------------------------------------------------------------------------

const CHAVE_RECUSA = "brd.regiao.consentimento";

export function lerRecusaLocal(): boolean {
  try {
    return localStorage.getItem(CHAVE_RECUSA) === "recusado";
  } catch {
    return false;
  }
}

export function marcarRecusaLocal() {
  try {
    localStorage.setItem(CHAVE_RECUSA, "recusado");
  } catch {}
}

export function limparRecusaLocal() {
  try {
    localStorage.removeItem(CHAVE_RECUSA);
  } catch {}
}

interface ConsentimentoLocalProps {
  /** Para quê o local será usado (ex.: "notícias da sua cidade e vizinhança"). */
  beneficio?: string;
  onRegiao: (r: Regiao) => void;
  onRecusar?: () => void;
  className?: string;
}

export function ConsentimentoLocal({
  beneficio = "notícias da sua cidade e vizinhança",
  onRegiao,
  onRecusar,
  className,
}: ConsentimentoLocalProps) {
  const [buscando, setBuscando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [cepAberto, setCepAberto] = useState(false);

  async function usarLocalizacao() {
    setBuscando(true);
    setErro(null);
    try {
      const r = await obterRegiaoPorGeolocation();
      limparRecusaLocal();
      onRegiao(r);
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "Não foi possível obter sua localização.");
      setCepAberto(true);
    } finally {
      setBuscando(false);
    }
  }

  function aplicarCep(e: { cep: string; logradouro: string; bairro: string; localidade: string; uf: string }) {
    limparRecusaLocal();
    onRegiao({ cidade: e.localidade, estado: e.uf, pais: "Brasil", cep: e.cep, bairro: e.bairro, logradouro: e.logradouro });
  }

  function recusar() {
    marcarRecusaLocal();
    onRecusar?.();
  }

  return (
    <div className={cn("flex flex-col items-center gap-3 py-4 text-center md:py-6", className)}>
      <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]">
        <MapPin className="h-6 w-6" aria-hidden />
      </span>
      <h2 className="text-xl font-bold tracking-tight text-[var(--cor-texto)]">Perto de você</h2>
      <p className="max-w-[42ch] text-sm leading-relaxed text-[var(--cor-texto-suave)]">
        Compartilhe sua localização para ver {beneficio}. Usamos só cidade e estado —{" "}
        <span className="font-medium text-[var(--cor-texto)]">nada é rastreado</span> e você pode apagar quando quiser.
      </p>
      <Button
        onClick={usarLocalizacao}
        disabled={buscando}
        size="lg"
        className="mt-1 min-h-[52px] gap-2 bg-[var(--cor-primaria)] px-8 text-base font-semibold text-[var(--cor-texto-invertido)] shadow-[var(--sombra-1)]"
      >
        <Locate className="h-5 w-5" aria-hidden /> {buscando ? "Localizando…" : "Compartilhar minha localização"}
      </Button>
      <p className="text-xs text-[var(--cor-texto-suave)]">Seu navegador vai pedir permissão — você pode dizer não.</p>
      {erro && (
        <div role="alert" className="w-full max-w-md rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">
          <p>{erro}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={usarLocalizacao}
            disabled={buscando}
            className="mt-2 min-h-[40px] border-[var(--cor-erro)] bg-transparent text-[var(--cor-erro)] hover:bg-[var(--cor-erro)] hover:text-white"
          >
            {buscando ? "Tentando…" : "Tentar novamente"}
          </Button>
        </div>
      )}
      <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
        <Collapsible open={cepAberto} onOpenChange={setCepAberto} className="w-full max-w-md">
          <CollapsibleTrigger asChild>
            <button className="text-xs text-[var(--cor-texto-suave)] underline underline-offset-4 hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">
              Prefiro digitar meu CEP
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-3 text-left">
            <BuscaCep compact onEndereco={aplicarCep} />
          </CollapsibleContent>
        </Collapsible>
        <button
          onClick={recusar}
          className="text-xs text-[var(--cor-texto-suave)] underline underline-offset-4 hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
        >
          Agora não
        </button>
      </div>
      <p className="flex items-center gap-1.5 text-xs text-[var(--cor-texto-suave)]">
        <ShieldCheck className="h-3.5 w-3.5" aria-hidden /> Local salvo só neste aparelho. Apague quando quiser.
      </p>
    </div>
  );
}
