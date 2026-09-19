"use client";

import { CompartilharLocalizacao } from "@/components/CompartilharLocalizacao";
import type { Regiao } from "@/lib/regiao";

// ---------------------------------------------------------------------------
// Consentimento de localização — padrão usado em "Perto de você" (Home).
// Camada fina sobre `CompartilharLocalizacao` (visual + fluxo únicos);
// aqui ficam só o contrato de props e a persistência da recusa.
// O Radar segue o mesmo padrão via `RadarLocalSimples`.
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
  return (
    <CompartilharLocalizacao
      beneficio={beneficio}
      className={className}
      onRegiao={(r) => {
        limparRecusaLocal();
        onRegiao(r);
      }}
      onRecusar={() => {
        marcarRecusaLocal();
        onRecusar?.();
      }}
    />
  );
}
