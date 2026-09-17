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

export async function obterRegiaoPorGeolocation(): Promise<Regiao> {
  if (!("geolocation" in navigator)) throw new Error("Geolocalização não disponível neste navegador.");
  const pos: GeolocationPosition = await new Promise((res, rej) =>
    navigator.geolocation.getCurrentPosition(res, rej, { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 })
  );
  const { latitude, longitude } = pos.coords;
  let cidade = "";
  let estado = "";
  let pais = "Brasil";
  let cep: string | undefined;
  let bairro: string | undefined;
  let logradouro: string | undefined;
  try {
    const r = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&zoom=10&addressdetails=1`, {
      headers: { Accept: "application/json" },
    });
    if (r.ok) {
      const j: unknown = await r.json();
      const a = (j as { address?: Record<string, string> })?.address || {};
      cidade = a.city || a.town || a.village || a.municipality || "";
      estado = a.state_code || a.state || "";
      if (estado.length > 2) estado = estado.slice(0, 2).toUpperCase();
      pais = a.country || "Brasil";
      cep = a.postcode;
      bairro = a.suburb || a.neighbourhood || a.quarter;
      logradouro = a.road || a.street;
    }
  } catch {}
  if (!cidade && !estado) throw new Error("Não foi possível identificar sua cidade. Digite seu CEP abaixo.");
  return { cidade, estado: estado.toUpperCase(), pais, cep, bairro, logradouro, lat: latitude, lon: longitude };
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
