import { useCallback, useEffect, useState } from "react";
import { obterStatusSistema } from "./api";

const CHAVE = "brd.premium-status";
const TTL_MS = 60_000;

interface CacheLido {
  valor: boolean;
  ts: number;
}

let cacheMemoria: CacheLido | null = null;

function lerLocal(): CacheLido | null {
  try {
    if (typeof window === "undefined" || !window.localStorage) return null;
    const raw = window.localStorage.getItem(CHAVE);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<CacheLido>;
    if (typeof parsed.valor !== "boolean" || typeof parsed.ts !== "number") return null;
    return { valor: parsed.valor, ts: parsed.ts };
  } catch {
    return null;
  }
}

function gravarLocal(valor: boolean, ts: number): void {
  try {
    if (typeof window === "undefined" || !window.localStorage) return;
    window.localStorage.setItem(CHAVE, JSON.stringify({ valor, ts }));
  } catch {
    // localStorage indisponível — segue só com memória.
  }
}

export function invalidarCachePremium(): void {
  cacheMemoria = null;
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.removeItem(CHAVE);
    }
  } catch {
    // ignora
  }
}

/** Flag Premium global. Falha aberta: API offline = `false` (tudo liberado). */
export async function obterPremiumAtivo(): Promise<boolean> {
  const agora = Date.now();
  if (cacheMemoria && agora - cacheMemoria.ts < TTL_MS) {
    return cacheMemoria.valor;
  }
  const local = lerLocal();
  if (local && agora - local.ts < TTL_MS) {
    cacheMemoria = local;
    return local.valor;
  }
  try {
    const status = await obterStatusSistema();
    const valor = status.premium_ativo === true;
    cacheMemoria = { valor, ts: agora };
    gravarLocal(valor, agora);
    return valor;
  } catch {
    return false;
  }
}

function lerValorInicial(): boolean | null {
  const local = lerLocal();
  if (local && Date.now() - local.ts < TTL_MS) return local.valor;
  return null;
}

export function usePremiumAtivo(): {
  ativo: boolean | null;
  liberado: boolean;
  recarregar(): void;
} {
  // `null` inicial nos dois lados (servidor e primeira render do cliente):
  // ler o localStorage aqui quebraria a hidratação (valor diverge do SSR).
  // O valor real é carregado no efeito abaixo, pós-hidratação.
  const [ativo, setAtivo] = useState<boolean | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setAtivo(lerValorInicial());
    let vivo = true;
    obterPremiumAtivo()
      .then((v) => {
        if (vivo) setAtivo(v);
      })
      .catch(() => {
        if (vivo) setAtivo(false);
      });
    return () => {
      vivo = false;
    };
  }, [tick]);

  const recarregar = useCallback(() => {
    invalidarCachePremium();
    setTick((n) => n + 1);
  }, []);

  return { ativo, liberado: ativo === false || ativo === null, recarregar };
}
