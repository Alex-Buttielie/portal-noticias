export interface EnderecoViaCep {
  cep: string;
  logradouro: string;
  complemento: string;
  bairro: string;
  localidade: string;
  uf: string;
  ibge: string;
  gia: string;
  ddd: string;
  siafi: string;
}

export interface BuscaCepOpts {
  signal?: AbortSignal;
}

const cacheCep = new Map<string, EnderecoViaCep>();
const cacheEndereco = new Map<string, EnderecoViaCep[]>();
// Dedup de requisições em voo: digitação com debounce + React StrictMode
// (efeito duplo) geravam 2 fetches idênticos; o segundo agora espera o primeiro.
const vooCep = new Map<string, Promise<EnderecoViaCep>>();
const vooEndereco = new Map<string, Promise<EnderecoViaCep[]>>();

function apiBase(): string | null {
  const b = (process.env.NEXT_PUBLIC_API_BASE_URL || "").replace(/\/$/, "");
  return b || null;
}

export function normalizaCep(cep: string): string {
  return cep.replace(/\D/g, "");
}

function validarCep(n: string) {
  if (n.length !== 8) throw new Error("CEP inválido. Informe 8 dígitos (ex: 01310-100).");
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
    if (res.status === 404) {
      let msg = "CEP não encontrado. Verifique o número digitado.";
      try {
        const j = (await res.json()) as { detail?: string };
        if (j?.detail) msg = j.detail;
      } catch {}
      throw new Error(msg);
    }
    if (res.status === 400) {
      let msg = "Busca inválida. Confira os campos.";
      try {
        const j = (await res.json()) as { detail?: string };
        if (j?.detail) msg = j.detail;
      } catch {}
      throw new Error(msg);
    }
    if (!res.ok) return null; // 502/429/5xx → fallback direto ao ViaCEP
    return (await res.json()) as T;
  } catch (e) {
    if (e instanceof Error && (e.message.includes("não encontrado") || e.message.includes("inválida")))
      throw e;
    return null; // rede/timeout/abort do proxy → fallback direto
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
}

async function diretoCep(n: string, signal?: AbortSignal): Promise<EnderecoViaCep> {
  let res: Response;
  try {
    res = await fetch(`https://viacep.com.br/ws/${n}/json/`, { signal });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new Error("Falha de rede ao consultar o CEP. Verifique sua conexão e tente novamente.");
  }
  if (!res.ok) throw new Error("Não foi possível consultar o CEP. Tente novamente em instantes.");
  let dados: EnderecoViaCep & { erro?: boolean };
  try {
    dados = await res.json();
  } catch {
    throw new Error("Resposta inválida do serviço de CEP.");
  }
  if ((dados as unknown as Record<string, unknown>).erro) throw new Error("CEP não encontrado. Verifique o número digitado.");
  return dados as EnderecoViaCep;
}

export async function buscarCep(cep: string, opts?: BuscaCepOpts): Promise<EnderecoViaCep> {
  const n = normalizaCep(cep);
  validarCep(n);
  if (opts?.signal?.aborted) throw new DOMException("Aborted", "AbortError");
  if (cacheCep.has(n)) return cacheCep.get(n)!;
  if (vooCep.has(n)) return vooCep.get(n)!;
  const p = (async () => {
    // Backend primeiro (cache compartilhado + rate-limit); fallback direto.
    const via = await viaProxy<EnderecoViaCep>(`/api/enderecos/cep/${n}/`, opts?.signal);
    const dados = via ?? (await diretoCep(n, opts?.signal));
    cacheCep.set(n, dados);
    return dados;
  })();
  vooCep.set(n, p);
  try {
    return await p;
  } finally {
    vooCep.delete(n);
  }
}

export async function buscarCepPorEndereco(
  uf: string,
  cidade: string,
  logradouro: string,
  opts?: BuscaCepOpts
): Promise<EnderecoViaCep[]> {
  const u = uf.trim().toUpperCase();
  const c = cidade.trim();
  const l = logradouro.trim();
  if (!/^[A-Z]{2}$/.test(u)) throw new Error("UF inválida. Use a sigla com 2 letras (ex: SP).");
  if (c.length < 3) throw new Error("Informe a cidade com ao menos 3 letras.");
  if (l.length < 3) throw new Error("Informe o logradouro com ao menos 3 letras.");
  if (opts?.signal?.aborted) throw new DOMException("Aborted", "AbortError");
  const chave = `${u}|${c.toLowerCase()}|${l.toLowerCase()}`;
  if (cacheEndereco.has(chave)) return cacheEndereco.get(chave)!;
  if (vooEndereco.has(chave)) return vooEndereco.get(chave)!;
  const p = (async () => {
    const via = await viaProxy<EnderecoViaCep[]>(
      `/api/enderecos/busca/?uf=${encodeURIComponent(u)}&cidade=${encodeURIComponent(c)}&logradouro=${encodeURIComponent(l)}`,
      opts?.signal
    );
    let lista: EnderecoViaCep[];
    if (via) {
      lista = via;
    } else {
      const url = `https://viacep.com.br/ws/${encodeURIComponent(u)}/${encodeURIComponent(c)}/${encodeURIComponent(l)}/json/`;
      let res: Response;
      try {
        res = await fetch(url, { signal: opts?.signal });
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") throw e;
        throw new Error("Falha de rede ao buscar endereço. Verifique sua conexão.");
      }
      if (!res.ok) throw new Error("Não foi possível buscar o endereço. Tente novamente.");
      let dados: unknown;
      try {
        dados = await res.json();
      } catch {
        throw new Error("Resposta inválida do serviço de CEP.");
      }
      if (!Array.isArray(dados)) throw new Error("CEP não encontrado para este endereço.");
      if (dados.length === 0) throw new Error("Nenhum endereço encontrado. Ajuste a busca.");
      lista = dados as EnderecoViaCep[];
    }
    cacheEndereco.set(chave, lista);
    for (const e of lista) {
      const nc = normalizaCep(e.cep);
      if (nc.length === 8) cacheCep.set(nc, e);
    }
    return lista;
  })();
  vooEndereco.set(chave, p);
  try {
    return await p;
  } finally {
    vooEndereco.delete(chave);
  }
}

export async function buscarSugestoesCep(_prefixo: string): Promise<EnderecoViaCep[]> {
  return [];
}
