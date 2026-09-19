"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import BuscaCep from "@/components/BuscaCep";
import {
  formatarRegiao,
  obterRegiaoPorGeolocation,
  obterRegiaoPorIP,
  regiaoDeEndereco,
  type Regiao,
} from "@/lib/regiao";
import { cn } from "@/lib/utils";
import { Loader2, Locate, MapPin, RotateCcw, X } from "lucide-react";

// ---------------------------------------------------------------------------
// CompartilharLocalizacao — componente ÚNICO de compartilhamento de local
// (Home "Perto de você", Radar, diálogo "Alterar região").
// Identidade própria: visual de radar (anéis + varredura + pino). Fluxo:
// ocios → localizando (GPS, prompt nativo do navegador) → pergunta-ip
// (o SISTEMA pergunta, inline) → pronto | erro (retry + CEP).
// Foco vai para o título do estado a cada transição; status em aria-live.
// ---------------------------------------------------------------------------

type Fase = "ocioso" | "localizando" | "pergunta-ip" | "erro";

function RadarVisual({ ativo, className }: { ativo?: boolean; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "relative inline-flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-full",
        "border border-[var(--cor-primaria)] bg-[var(--cor-primaria-suave)]",
        className
      )}
    >
      <span aria-hidden className="absolute inset-2 rounded-full border border-[var(--cor-primaria)] opacity-40" />
      <span aria-hidden className="absolute inset-4 rounded-full border border-[var(--cor-primaria)] opacity-60" />
      <span
        aria-hidden
        className={cn(
          "absolute inset-0 rounded-full motion-safe:animate-ping",
          ativo ? "[animation-duration:1s] opacity-30" : "[animation-duration:2.5s] opacity-20"
        )}
        style={{ background: "radial-gradient(circle, var(--cor-primaria) 0%, transparent 70%)" }}
      />
      <MapPin className="relative h-6 w-6 text-[var(--cor-primaria)]" aria-hidden />
    </span>
  );
}

export function CompartilharLocalizacao({
  onRegiao,
  onRecusar,
  beneficio = "notícias da sua cidade e vizinhança",
  compacto = false,
  ocultarCep = false,
  mostrarRecusa = true,
  className,
}: {
  onRegiao: (r: Regiao) => void;
  onRecusar?: () => void;
  beneficio?: string;
  compacto?: boolean;
  ocultarCep?: boolean;
  mostrarRecusa?: boolean;
  className?: string;
}) {
  const [fase, setFase] = useState<Fase>("ocioso");
  const [erro, setErro] = useState<string | null>(null);
  const [cepAberto, setCepAberto] = useState(false);
  const [regiaoIp, setRegiaoIp] = useState<Regiao | null>(null);
  const tituloRef = useRef<HTMLHeadingElement>(null);

  // Leva o foco ao título quando o estado muda (menos no início).
  useEffect(() => {
    if (fase !== "ocioso") tituloRef.current?.focus({ preventScroll: true });
  }, [fase]);

  async function compartilhar() {
    setFase("localizando");
    setErro(null);
    let erroGps = "Não foi possível obter sua localização.";
    try {
      const r = await obterRegiaoPorGeolocation();
      onRegiao(r);
      return;
    } catch (e: unknown) {
      if (e instanceof Error && e.message) erroGps = e.message;
    }
    // GPS indisponível/bloqueado → o SISTEMA pergunta (IP), inline.
    try {
      const r = await obterRegiaoPorIP();
      setRegiaoIp(r);
      setFase("pergunta-ip");
    } catch {
      setErro(erroGps);
      setCepAberto(true);
      setFase("erro");
    }
  }

  function usarRegiaoIp() {
    if (!regiaoIp) return;
    onRegiao(regiaoIp);
  }

  if (fase === "pergunta-ip" && regiaoIp) {
    return (
      <div className={cn("flex flex-col items-center gap-3 py-4 text-center", className)}>
        <RadarVisual />
        <div aria-live="polite" className="space-y-1">
          <h2 ref={tituloRef} tabIndex={-1} className="text-lg font-bold text-[var(--cor-texto)] focus-visible:outline-none">
            Detectamos {formatarRegiao(regiaoIp)}. É você?
          </h2>
          <p className="text-sm text-[var(--cor-texto-suave)]">
            Pela sua conexão — usamos só cidade e estado, nada é rastreado.
          </p>
        </div>
        <div className="flex w-full max-w-md flex-col gap-2 sm:flex-row">
          <Button
            type="button"
            onClick={usarRegiaoIp}
            className="min-h-[48px] flex-1 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]"
          >
            Sim, usar {formatarRegiao(regiaoIp)}
          </Button>
          {!ocultarCep && (
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setFase("erro");
                setCepAberto(true);
              }}
              className="min-h-[48px] flex-1"
            >
              Digitar CEP
            </Button>
          )}
        </div>
      </div>
    );
  }

  if (fase === "erro") {
    return (
      <div className={cn("flex flex-col items-center gap-3 py-4 text-center", className)}>
        <RadarVisual />
        <div aria-live="polite" className="w-full max-w-md space-y-2">
          <h2 ref={tituloRef} tabIndex={-1} className="text-lg font-bold text-[var(--cor-texto)] focus-visible:outline-none">
            Não conseguimos te localizar
          </h2>
          {erro && (
            <p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">
              {erro}
            </p>
          )}
          <Button
            type="button"
            variant="outline"
            onClick={compartilhar}
            className="min-h-[44px] w-full gap-2"
          >
            <RotateCcw className="h-4 w-4" aria-hidden /> Tentar novamente
          </Button>
        </div>
        {!ocultarCep && (
          <Collapsible open={cepAberto} onOpenChange={setCepAberto} className="w-full max-w-md">
            <CollapsibleTrigger asChild>
              <button className="text-xs text-[var(--cor-texto-suave)] underline underline-offset-4 hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">
                Prefiro digitar meu CEP
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent className="pt-3 text-left">
              <BuscaCep compact onEndereco={(e) => onRegiao(regiaoDeEndereco(e))} />
            </CollapsibleContent>
          </Collapsible>
        )}
      </div>
    );
  }

  return (
    <div className={cn("flex gap-3", compacto ? "flex-row items-center" : "flex-col items-center py-4 text-center md:py-6", className)}>
      <RadarVisual ativo={fase === "localizando"} className={compacto ? "h-11 w-11" : undefined} />
      <div className={cn("min-w-0", compacto ? "flex-1 text-left" : "flex flex-col items-center gap-3")}>
        {!compacto && (
          <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)]">
            Perto de você
          </p>
        )}
        <h2 className={cn("font-bold tracking-tight text-[var(--cor-texto)]", compacto ? "text-sm" : "text-xl")}>
          Onde você está?
        </h2>
        <p className={cn("leading-relaxed text-[var(--cor-texto-suave)]", compacto ? "text-xs" : "max-w-[42ch] text-sm")}>
          Compartilhe para ver {beneficio}. Só cidade e estado — nada é rastreado e você apaga quando quiser.
        </p>
        <div className={cn("flex gap-2", compacto ? "mt-2 flex-row" : "mt-1 flex-col sm:flex-row sm:items-center")}>
          <Button
            type="button"
            onClick={compartilhar}
            disabled={fase === "localizando"}
            size={compacto ? "sm" : "lg"}
            className="min-h-[44px] gap-2 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] shadow-[var(--sombra-1)] hover:bg-[var(--cor-primaria-hover)]"
          >
            {fase === "localizando" ? (
              <>
                <Loader2 className="h-4 w-4 motion-safe:animate-spin" aria-hidden /> Localizando…
              </>
            ) : (
              <>
                <Locate className="h-4 w-4" aria-hidden />{" "}
                {compacto ? "Detectar" : "Compartilhar minha localização"}
              </>
            )}
          </Button>
          {!compacto && !ocultarCep && (
            <Collapsible open={cepAberto} onOpenChange={setCepAberto}>
              <CollapsibleTrigger asChild>
                <button className="min-h-[44px] px-2 text-xs text-[var(--cor-texto-suave)] underline underline-offset-4 hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">
                  Prefiro digitar meu CEP
                </button>
              </CollapsibleTrigger>
              <CollapsibleContent className="pt-3 text-left">
                <BuscaCep compact onEndereco={(e) => onRegiao(regiaoDeEndereco(e))} />
              </CollapsibleContent>
            </Collapsible>
          )}
          {mostrarRecusa && !compacto && (
            <button
              type="button"
              onClick={onRecusar}
              className="min-h-[44px] px-2 text-xs text-[var(--cor-texto-suave)] underline underline-offset-4 hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
            >
              Agora não
            </button>
          )}
        </div>
        <p className="text-xs text-[var(--cor-texto-suave)]">Seu navegador vai pedir permissão — você pode dizer não.</p>
      </div>
    </div>
  );
}

export function ChipRegiao({
  regiao,
  onTrocar,
  onLimpar,
}: {
  regiao: Regiao;
  onTrocar?: () => void;
  onLimpar?: () => void;
}) {
  return (
    <p className="flex flex-wrap items-center gap-2 text-sm">
      <Badge variant="outline" className="gap-1 border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]">
        <MapPin className="h-3 w-3 text-[var(--cor-primaria)]" aria-hidden />
        {formatarRegiao(regiao)}
      </Badge>
      {onTrocar && (
        <button
          type="button"
          onClick={onTrocar}
          className="min-h-[36px] text-xs text-[var(--cor-primaria)] underline underline-offset-4 hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
        >
          Trocar
        </button>
      )}
      {onLimpar && (
        <button
          type="button"
          onClick={onLimpar}
          aria-label="Apagar região salva"
          className="inline-flex min-h-[36px] min-w-[36px] items-center justify-center rounded-full text-[var(--cor-texto-suave)] hover:bg-[var(--cor-fundo-elevado)] hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
      )}
    </p>
  );
}
