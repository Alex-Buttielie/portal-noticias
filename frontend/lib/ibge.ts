let cacheEstados: { sigla: string; nome: string }[] | null = null;
const cacheMunicipios = new Map<string, string[]>();

export async function listarEstados(): Promise<{ sigla: string; nome: string }[]> {
  if (cacheEstados) return cacheEstados;
  let res: Response;
  try {
    res = await fetch("https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome");
  } catch {
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
}

export async function listarMunicipios(uf: string): Promise<string[]> {
  const u = uf.trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(u)) throw new Error("UF inválida.");
  if (cacheMunicipios.has(u)) return cacheMunicipios.get(u)!;
  let res: Response;
  try {
    res = await fetch(`https://servicodados.ibge.gov.br/api/v1/localidades/estados/${u}/municipios?orderBy=nome`);
  } catch {
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
}
