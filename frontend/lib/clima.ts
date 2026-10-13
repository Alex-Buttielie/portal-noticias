/**
 * Clima — Open-Meteo (api.open-meteo.com), sem chave para uso não
 * comercial (ver open-meteo.com/en/docs). Só busca quando o leitor já tem
 * uma `Regiao` salva (mesmo consentimento de localização de
 * `components/SecaoRegiao.tsx`) — nunca geolocaliza por conta própria.
 * Cache em sessionStorage (30 min) pra não bater na API a cada navegação.
 */

import type { Regiao } from "./regiao";

export interface PrevisaoDia {
  data: string; // ISO yyyy-mm-dd
  max: number;
  min: number;
  codigo: number;
}

export interface Clima {
  cidade: string;
  temperaturaAtual: number;
  codigoAtual: number;
  previsao: PrevisaoDia[]; // inclui hoje
}

const CHAVE_CACHE = "brd.clima.v1";
const TTL_MS = 30 * 60 * 1000;

interface CacheEntry {
  chave: string;
  expiraEm: number;
  clima: Clima;
}

function lerCache(chave: string): Clima | null {
  try {
    const bruto = sessionStorage.getItem(CHAVE_CACHE);
    if (!bruto) return null;
    const entrada = JSON.parse(bruto) as CacheEntry;
    if (entrada.chave !== chave || entrada.expiraEm < Date.now()) return null;
    return entrada.clima;
  } catch {
    return null;
  }
}

function salvarCache(chave: string, clima: Clima): void {
  try {
    const entrada: CacheEntry = { chave, expiraEm: Date.now() + TTL_MS, clima };
    sessionStorage.setItem(CHAVE_CACHE, JSON.stringify(entrada));
  } catch {
    // sessionStorage indisponível — sem cache, busca de novo na próxima
  }
}

async function geocodificar(cidade: string, estado: string): Promise<{ lat: number; lon: number } | null> {
  try {
    const resp = await fetch(
      `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(cidade)}&count=5&language=pt&country=BR`
    );
    if (!resp.ok) return null;
    const dados = await resp.json();
    const resultados: Array<{ latitude: number; longitude: number; admin1?: string }> = dados.results || [];
    if (resultados.length === 0) return null;
    const comEstado = resultados.find((r) => (r.admin1 || "").toLowerCase().includes(estado.toLowerCase()));
    const escolhido = comEstado || resultados[0];
    return { lat: escolhido.latitude, lon: escolhido.longitude };
  } catch {
    return null;
  }
}

/** Busca o clima pra uma região já salva (consentida). `null` em qualquer
 * falha — o widget some, nunca mostra número inventado. */
export async function obterClima(regiao: Regiao): Promise<Clima | null> {
  if (typeof window === "undefined") return null;
  let lat = regiao.lat;
  let lon = regiao.lon;
  if (lat == null || lon == null) {
    if (!regiao.cidade) return null;
    const geo = await geocodificar(regiao.cidade, regiao.estado || "");
    if (!geo) return null;
    lat = geo.lat;
    lon = geo.lon;
  }
  const chave = `${lat.toFixed(2)},${lon.toFixed(2)}`;
  const emCache = lerCache(chave);
  if (emCache) return emCache;

  try {
    const resp = await fetch(
      `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,weather_code&daily=temperature_2m_max,temperature_2m_min,weather_code&timezone=America%2FSao_Paulo&forecast_days=4`
    );
    if (!resp.ok) return null;
    const dados = await resp.json();
    if (!dados.current || !dados.daily) return null;
    const clima: Clima = {
      cidade: regiao.cidade || "",
      temperaturaAtual: Math.round(dados.current.temperature_2m),
      codigoAtual: dados.current.weather_code,
      previsao: (dados.daily.time as string[]).map((data: string, i: number) => ({
        data,
        max: Math.round(dados.daily.temperature_2m_max[i]),
        min: Math.round(dados.daily.temperature_2m_min[i]),
        codigo: dados.daily.weather_code[i],
      })),
    };
    salvarCache(chave, clima);
    return clima;
  } catch {
    return null;
  }
}

/** Tabela WMO (padrão aberto, open-meteo.com/en/docs → WMO Weather
 * interpretation codes) — rótulo em pt-BR + nome do ícone lucide-react. */
export function interpretarCodigoClima(codigo: number): { rotulo: string; icone: "sol" | "nublado" | "chuva" | "tempestade" | "neve" | "neblina" } {
  if (codigo === 0) return { rotulo: "Céu limpo", icone: "sol" };
  if (codigo <= 2) return { rotulo: "Parcialmente nublado", icone: "sol" };
  if (codigo === 3) return { rotulo: "Nublado", icone: "nublado" };
  if (codigo === 45 || codigo === 48) return { rotulo: "Neblina", icone: "neblina" };
  if (codigo >= 51 && codigo <= 67) return { rotulo: "Chuva", icone: "chuva" };
  if (codigo >= 71 && codigo <= 77) return { rotulo: "Neve", icone: "neve" };
  if (codigo >= 80 && codigo <= 82) return { rotulo: "Pancadas de chuva", icone: "chuva" };
  if (codigo >= 85 && codigo <= 86) return { rotulo: "Pancadas de neve", icone: "neve" };
  if (codigo >= 95) return { rotulo: "Tempestade", icone: "tempestade" };
  return { rotulo: "—", icone: "nublado" };
}
