let cacheEstados: { sigla: string; nome: string }[] | null = null;
const cacheMunicipios = new Map<string, string[]>();
const vooMunicipios = new Map<string, Promise<string[]>>();
let vooEstados: Promise<{ sigla: string; nome: string }[]> | null = null;

function apiBase(): string | null {
  const b = (process.env.NEXT_PUBLIC_API_BASE_URL || "").replace(/\/$/, "");
  return b || null;
}

async function viaProxy<T>(path: string, signal?: AbortSignal): Promise<T | null> {
  const base = apiBase();
  if (!base) return null;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 6000);
  const onAbort = () => ctrl.abort();
  signal?.addEventListener("abort", onAbort, { once: true });
  try {
    const res = await fetch(`${base}${path}`, { signal: ctrl.signal });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
}

export async function listarEstados(opts?: { signal?: AbortSignal }): Promise<{ sigla: string; nome: string }[]> {
  if (cacheEstados) return cacheEstados;
  if (vooEstados) return vooEstados;
  vooEstados = (async () => {
    const via = await viaProxy<{ sigla: string; nome: string }[]>("/api/enderecos/estados/", opts?.signal);
    if (via) {
      cacheEstados = via;
      return via;
    }
    let res: Response;
    try {
      res = await fetch("https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome", {
        signal: opts?.signal,
      });
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") throw e;
      throw new Error("Falha de rede ao carregar estados.");
    }
    if (!res.ok) throw new Error("Não foi possível carregar estados.");
    let dados: unknown;
    try {
      dados = await res.json();
    } catch {
      throw new Error("Resposta inválida ao carregar estados.");
    }
    if (!Array.isArray(dados)) throw new Error("Resposta inválida ao carregar estados.");
    const lista = (dados as Array<{ sigla: string; nome: string }>).map((e) => ({ sigla: e.sigla, nome: e.nome }));
    cacheEstados = lista;
    return lista;
  })();
  try {
    return await vooEstados;
  } finally {
    vooEstados = null;
  }
}

export async function listarMunicipios(uf: string, opts?: { signal?: AbortSignal }): Promise<string[]> {
  const u = uf.trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(u)) throw new Error("UF inválida.");
  if (cacheMunicipios.has(u)) return cacheMunicipios.get(u)!;
  if (vooMunicipios.has(u)) return vooMunicipios.get(u)!;
  const p = (async () => {
    const via = await viaProxy<string[]>(`/api/enderecos/estados/${u}/municipios/`, opts?.signal);
    if (via) {
      cacheMunicipios.set(u, via);
      return via;
    }
    let res: Response;
    try {
      res = await fetch(`https://servicodados.ibge.gov.br/api/v1/localidades/estados/${u}/municipios?orderBy=nome`, {
        signal: opts?.signal,
      });
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") throw e;
      throw new Error("Falha de rede ao carregar municípios.");
    }
    if (!res.ok) throw new Error("Não foi possível carregar municípios.");
    let dados: unknown;
    try {
      dados = await res.json();
    } catch {
      throw new Error("Resposta inválida ao carregar municípios.");
    }
    if (!Array.isArray(dados)) throw new Error("Resposta inválida ao carregar municípios.");
    const lista = (dados as Array<{ nome: string }>).map((m) => m.nome);
    cacheMunicipios.set(u, lista);
    return lista;
  })();
  vooMunicipios.set(u, p);
  try {
    return await p;
  } finally {
    vooMunicipios.delete(u);
  }
}
