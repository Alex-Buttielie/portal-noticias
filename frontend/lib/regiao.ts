export interface Regiao {
  cidade: string;
  estado: string;
  pais: string;
  cep?: string;
  bairro?: string;
  logradouro?: string;
  lat?: number;
  lon?: number;
}

const CHAVE = "brd.regiao.v1";

export function carregarRegiao(): Regiao | null {
  try {
    const raw = localStorage.getItem(CHAVE);
    if (raw) return JSON.parse(raw) as Regiao;
  } catch {}
  return null;
}

export function salvarRegiao(r: Regiao) {
  try {
    localStorage.setItem(CHAVE, JSON.stringify(r));
  } catch {}
}

export function limparRegiao() {
  try { localStorage.removeItem(CHAVE); } catch {}
}

export function formatarRegiao(r: Regiao): string {
  if (r.cidade && r.estado) return `${r.cidade}, ${r.estado}`;
  if (r.cidade) return r.cidade;
  if (r.estado) return r.estado;
  return r.pais || "Sua região";
}

/** Mapeia o retorno do BuscaCep para Regiao (usado nos 3 fluxos). */
export function regiaoDeEndereco(e: {
  cep: string;
  logradouro: string;
  bairro: string;
  localidade: string;
  uf: string;
}): Regiao {
  return {
    cidade: e.localidade,
    estado: e.uf,
    pais: "Brasil",
    cep: e.cep,
    bairro: e.bairro,
    logradouro: e.logradouro,
  };
}

function apiBase(): string | null {
  const b = (process.env.NEXT_PUBLIC_API_BASE_URL || "").replace(/\/$/, "");
  return b || null;
}

export type EstadoPermissaoGeo = "granted" | "prompt" | "denied" | "desconhecido";

/** Consulta a Permissions API sem pedir nada ao usuário. */
export async function estadoPermissaoLocalizacao(): Promise<EstadoPermissaoGeo> {
  try {
    type Perms = { query(o: { name: string }): Promise<{ state: string }> };
    const perms = (navigator as Navigator & { permissions?: Perms }).permissions;
    if (!perms?.query) return "desconhecido";
    const st = await perms.query({ name: "geolocation" });
    if (st.state === "granted" || st.state === "prompt" || st.state === "denied") return st.state;
    return "desconhecido";
  } catch {
    return "desconhecido";
  }
}

export const MENSAGEM_PERMISSAO_BLOQUEADA =
  "O acesso à localização está bloqueado para este site — por isso o navegador nem chega a perguntar. " +
  "Toque no cadeado ao lado do endereço, libere a Localização e toque em Tentar novamente. " +
  "Ou digite seu CEP abaixo.";

export const MENSAGEM_NEGADA_AGORA =
  "Você optou por não compartilhar agora — sem problema. Toque em Tentar novamente que o navegador " +
  "pergunta de novo, ou digite seu CEP abaixo.";

function obterPosicao(): Promise<GeolocationPosition> {
  if (typeof navigator === "undefined" || !("geolocation" in navigator)) {
    throw new Error("Geolocalização não disponível neste navegador. Digite seu CEP abaixo.");
  }
  return new Promise<GeolocationPosition>((res, rej) =>
    navigator.geolocation.getCurrentPosition(res, rej, {
      enableHighAccuracy: false,
      timeout: 15000,
      maximumAge: 600000,
    })
  ).catch(async (e: unknown) => {
    // GeolocationPositionError é DOMException (não instanceof Error em
    // vários browsers) — mapear pelo código para mensagem acionável.
    // IMPORTANTE: nunca bloqueamos a chamada antes da hora. O fluxo natural
    // é sempre: clique → getCurrentPosition → o NAVEGADOR pergunta (Allow/
    // Bloquear). Só depois da resposta adaptamos a mensagem — inclusive
    // distinguindo "negou agora" (tenta de novo que ele pergunta) de
    // "bloqueado persistente" (aí sim, cadeado).
    const code = typeof e === "object" && e !== null ? (e as { code?: number }).code : undefined;
    if (code === 1) {
      const estado = await estadoPermissaoLocalizacao();
      if (estado === "denied") throw new Error(MENSAGEM_PERMISSAO_BLOQUEADA);
      throw new Error(MENSAGEM_NEGADA_AGORA);
    }
    if (code === 2) {
      throw new Error("Sinal de localização indisponível no momento. Tente de novo ou digite seu CEP abaixo.");
    }
    if (code === 3) {
      throw new Error("Demorou demais para obter o sinal. Tente de novo em local aberto ou digite seu CEP abaixo.");
    }
    throw new Error("Não foi possível obter sua localização. Tente de novo ou digite seu CEP abaixo.");
  });
}

type Reverso = {
  cidade?: string;
  estado?: string;
  pais?: string;
  cep?: string;
  bairro?: string;
  logradouro?: string;
};

async function reverterViaProxy(lat: number, lon: number): Promise<Reverso | null> {
  const base = apiBase();
  if (!base) return null;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 8000);
  try {
    const r = await fetch(`${base}/api/enderecos/reverso/?lat=${lat}&lon=${lon}`, {
      signal: ctrl.signal,
      headers: { Accept: "application/json" },
    });
    if (!r.ok) return null; // 404/502/429 → fallback direto ao Nominatim
    return (await r.json()) as Reverso;
  } catch {
    return null; // proxy fora/timeout → fallback direto
  } finally {
    clearTimeout(timer);
  }
}

async function reverterDireto(lat: number, lon: number): Promise<Reverso | null> {
  try {
    const r = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=10&addressdetails=1`,
      { headers: { Accept: "application/json" } }
    );
    if (!r.ok) return null;
    const j: unknown = await r.json();
    const a = (j as { address?: Record<string, string> })?.address || {};
    return {
      cidade: a.city || a.town || a.village || a.municipality || "",
      estado: a.state_code || a.state || "",
      pais: a.country || "Brasil",
      cep: a.postcode,
      bairro: a.suburb || a.neighbourhood || a.quarter,
      logradouro: a.road || a.street,
    };
  } catch {
    return null;
  }
}

export async function obterRegiaoPorGeolocation(): Promise<Regiao> {  // Fluxo natural, sem gate: o navegador sempre tem a chance de perguntar.
  const pos = await obterPosicao();
  const { latitude, longitude } = pos.coords;
  // Proxy do backend primeiro (User-Agent identificável + cache; o Nominatim
  // bloqueia 403/429 o tráfego direto do navegador com frequência).
  const rev = (await reverterViaProxy(latitude, longitude)) ?? (await reverterDireto(latitude, longitude));
  let cidade = rev?.cidade || "";
  let estado = rev?.estado || "";
  if (estado.length > 2) estado = estado.slice(0, 2).toUpperCase();
  if (!cidade && !estado) throw new Error("Não foi possível identificar sua cidade. Digite seu CEP abaixo.");
  return {
    cidade,
    estado: estado.toUpperCase(),
    pais: rev?.pais || "Brasil",
    cep: rev?.cep,
    bairro: rev?.bairro,
    logradouro: rev?.logradouro,
    lat: latitude,
    lon: longitude,
  };
}

/**
 * Região aproximada pela conexão (IP) — sem GPS, sem permissão do navegador.
 * Usada como fallback automático quando o GPS falha/bloqueia: o SISTEMA
 * pergunta ao usuário (diálogo próprio) se aceita a região detectada, então
 * o fluxo sempre continua mesmo sem o prompt nativo.
 */
export async function obterRegiaoPorIP(): Promise<Regiao> {
  const base = apiBase();
  if (base) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
    try {
      const r = await fetch(`${base}/api/enderecos/por-ip/`, {
        signal: ctrl.signal,
        headers: { Accept: "application/json" },
      });
      if (r.ok) {
        const j = (await r.json()) as Reverso & { fonte?: string };
        if (j?.cidade || j?.estado) {
          return {
            cidade: j.cidade || "",
            estado: (j.estado || "").toUpperCase(),
            pais: j.pais || "Brasil",
            cep: j.cep || undefined,
          };
        }
      }
    } catch {
      /* cai para o fallback direto */
    } finally {
      clearTimeout(timer);
    }
  }
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 6000);
    try {
      const r = await fetch("https://ipapi.co/json/", { signal: ctrl.signal });
      if (r.ok) {
        const j = (await r.json()) as {
          city?: string;
          region_code?: string;
          country_name?: string;
          postal?: string;
        };
        if (j?.city || j?.region_code) {
          return {
            cidade: j.city || "",
            estado: (j.region_code || "").toUpperCase(),
            pais: j.country_name || "Brasil",
            cep: j.postal || undefined,
          };
        }
      }
    } finally {
      clearTimeout(timer);
    }
  } catch {
    /* sem detecção */
  }
  throw new Error("Não foi possível detectar sua região pela conexão. Digite seu CEP abaixo.");
}

export function cidadesVizinhasMock(cidade: string, estado: string): string[] {
  const base = cidade.trim();
  if (!base) return [];
  const sfx = ["Centro", "Zona Sul", "Zona Norte", "Leste", "Oeste"];
  const pool: Record<string, string[]> = {
    "São Paulo": ["Guarulhos", "Osasco", "Santo André", "São Bernardo do Campo", "Barueri"],
    "Rio de Janeiro": ["Niterói", "Duque de Caxias", "São Gonçalo", "Nova Iguaçu", "Belford Roxo"],
    "Belo Horizonte": ["Contagem", "Betim", "Nova Lima", "Sabará", "Santa Luzia"],
    "Brasília": ["Taguatinga", "Ceilândia", "Águas Claras", "Gama", "Samambaia"],
    "Salvador": ["Lauro de Freitas", "Camaçari", "Simões Filho", "Candeias", "Dias d'Ávila"],
    "Curitiba": ["São José dos Pinhais", "Colombo", "Pinhais", "Araucária", "Campo Largo"],
    "Porto Alegre": ["Canoas", "Viamão", "Gravataí", "Alvorada", "Cachoeirinha"],
    "Recife": ["Olinda", "Jaboatão dos Guararapes", "Paulista", "Camaragibe", "São Lourenço da Mata"],
    "Fortaleza": ["Caucaia", "Maracanaú", "Eusébio", "Aquiraz", "Maranguape"],
  };
  if (pool[base]) return pool[base];
  return sfx.slice(0, 4).map((s) => `${base} — ${s}`);
}

export function ordenarPorProximidade<T extends { cidade?: string; estado?: string }>(itens: T[], regiao: Regiao): T[] {
  const c = (regiao.cidade || "").toLowerCase();
  const e = (regiao.estado || "").toLowerCase();
  return [...itens].sort((a, b) => {
    const ac = (a.cidade || "").toLowerCase() === c ? 0 : (a.estado || "").toLowerCase() === e ? 1 : 2;
    const bc = (b.cidade || "").toLowerCase() === c ? 0 : (b.estado || "").toLowerCase() === e ? 1 : 2;
    return ac - bc;
  });
}
