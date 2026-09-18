// Detecção de dispositivo sem dependências externas.
// - Servidor (RSC/middleware): `perfilPorUserAgent(ua)` a partir do header.
// - Cliente: `observarDispositivo(cb)` com matchMedia + touch + orientação,
//   pensado para mobile/tablet/desktop reais (iOS Safari, Android Chrome,
//   PWA standalone, dobráveis em modo estreito).

import {
  PERFIL_PADRAO_DESKTOP,
  type ClasseDispositivo,
  type Orientacao,
  type PerfilDispositivo,
  type SistemaOperacional,
  type TipoEntrada,
} from "./tipos";

export const BREAKPOINTS = {
  /** até 639px: phones */
  mobileMax: 639,
  /** 640–1023px: phones grandes / tablets pequenos */
  tabletMax: 1023,
} as const;

export function classePorLargura(largura: number): ClasseDispositivo {
  if (largura >= 1536) return "tv";
  if (largura > BREAKPOINTS.tabletMax) return "desktop";
  if (largura > BREAKPOINTS.mobileMax) return "tablet";
  return "mobile";
}

export function soPorUserAgent(ua: string): SistemaOperacional {
  const s = ua.toLowerCase();
  if (/iphone|ipad|ipod/.test(s)) return "ios";
  if (/android/.test(s)) return "android";
  if (/windows/.test(s)) return "windows";
  if (/mac os|macintosh/.test(s)) return "macos";
  if (/linux/.test(s)) return "linux";
  return "outro";
}

/** Classificação SSR barata só com o User-Agent (sem largura real). */
export function perfilPorUserAgent(ua: string | null | undefined): PerfilDispositivo {
  const so = soPorUserAgent(ua ?? "");
  const s = (ua ?? "").toLowerCase();
  const ehMobile = /iphone|ipod|android.*mobile|mobile/.test(s);
  const ehTablet = /ipad|android(?!.*mobile)|tablet/.test(s);
  const classe: ClasseDispositivo = ehTablet ? "tablet" : ehMobile ? "mobile" : "desktop";
  const entrada: TipoEntrada = classe === "desktop" ? "mouse" : "touch";
  return {
    ...PERFIL_PADRAO_DESKTOP,
    classe,
    so,
    entrada,
    orientacao: classe === "desktop" ? "landscape" : "portrait",
    largura: classe === "mobile" ? 390 : classe === "tablet" ? 768 : 1280,
    altura: classe === "mobile" ? 844 : classe === "tablet" ? 1024 : 800,
    standalone: false,
    temSafeArea: classe !== "desktop" && (so === "ios" || so === "android"),
  };
}

function entradaAtual(): TipoEntrada {
  if (typeof window === "undefined") return "mouse";
  try {
    const coarse = window.matchMedia("(pointer: coarse)").matches;
    const fine = window.matchMedia("(pointer: fine)").matches;
    if (coarse && fine) return "hibrido";
    if (coarse) return "touch";
    const temTouch =
      "ontouchstart" in window || (navigator?.maxTouchPoints ?? 0) > 0;
    return temTouch ? "touch" : "mouse";
  } catch {
    return "mouse";
  }
}

function snapshotCliente(): PerfilDispositivo {
  const largura = window.innerWidth;
  const altura = window.innerHeight;
  const orientacao: Orientacao = altura >= largura ? "portrait" : "landscape";
  const so = soPorUserAgent(navigator.userAgent);
  const standalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true;
  const entrada = entradaAtual();
  return {
    classe: classePorLargura(largura),
    so,
    entrada,
    orientacao,
    largura,
    altura,
    standalone,
    temSafeArea: entrada !== "mouse" && (so === "ios" || so === "android"),
  };
}

/**
 * Modo de navegação derivado do perfil — fonte única usada pelo
 * `NavegacaoAdaptativa` e pelo `DeviceProvider` (atributo `data-nav`).
 * - "nenhuma": desktop/TV (Header superior cobre).
 * - "trilho": tablet de verdade em paisagem (menor dimensão >= 600px).
 * - "inferior": todo o resto (mobile retrato/paisagem, tablet retrato,
 *   celular em paisagem — nunca ficam sem navegação).
 */
export function modoNavegacao(perfil: PerfilDispositivo): "trilho" | "inferior" | "nenhuma" {
  if (perfil.classe === "desktop" || perfil.classe === "tv") return "nenhuma";
  const menorDimensao = Math.min(perfil.largura, perfil.altura);
  if (perfil.classe === "tablet" && perfil.orientacao === "landscape" && menorDimensao >= 600) {
    return "trilho";
  }
  return "inferior";
}

/**
 * Observa mudanças (resize/orientação/display-mode). Retorna função de
 * unsubscribe. Seguro para SSR (no-op fora do browser).
 */
export function observarDispositivo(
  onChange: (perfil: PerfilDispositivo) => void
): () => void {
  if (typeof window === "undefined") return () => {};
  let ultimo = JSON.stringify(snapshotCliente());
  onChange(JSON.parse(ultimo) as PerfilDispositivo);

  const emitir = () => {
    try {
      const atual = snapshotCliente();
      const chave = JSON.stringify(atual);
      if (chave !== ultimo) {
        ultimo = chave;
        onChange(atual);
      }
    } catch {
      /* ignora leituras transitórias durante rotação */
    }
  };

  // Debounce leve: rotação/resize disparam em rajada no mobile.
  let timer: ReturnType<typeof setTimeout> | null = null;
  const agendado = () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(emitir, 100);
  };

  window.addEventListener("resize", agendado, { passive: true });
  window.addEventListener("orientationchange", agendado, { passive: true });
  const mql = window.matchMedia("(display-mode: standalone)");
  const onMql = () => agendado();
  try {
    mql.addEventListener("change", onMql);
  } catch {
    // Safari antigo: addListener
    (mql as MediaQueryList & { addListener?: (fn: () => void) => void }).addListener?.(onMql);
  }
  return () => {
    window.removeEventListener("resize", agendado);
    window.removeEventListener("orientationchange", agendado);
    try {
      mql.removeEventListener("change", onMql);
    } catch {
      (mql as MediaQueryList & { removeListener?: (fn: () => void) => void }).removeListener?.(onMql);
    }
    if (timer) clearTimeout(timer);
  };
}
