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

const cacheCep = new Map<string, EnderecoViaCep>();
const cacheEndereco = new Map<string, EnderecoViaCep[]>();

export function normalizaCep(cep: string): string {
  return cep.replace(/\D/g, "");
}

function validarCep(n: string) {
  if (n.length !== 8) throw new Error("CEP inválido. Informe 8 dígitos (ex: 01310-100).");
}

export async function buscarCep(cep: string): Promise<EnderecoViaCep> {
  const n = normalizaCep(cep);
  validarCep(n);
  if (cacheCep.has(n)) return cacheCep.get(n)!;
  let res: Response;
  try {
    res = await fetch(`https://viacep.com.br/ws/${n}/json/`);
  } catch {
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
  cacheCep.set(n, dados as EnderecoViaCep);
  return dados as EnderecoViaCep;
}

export async function buscarCepPorEndereco(uf: string, cidade: string, logradouro: string): Promise<EnderecoViaCep[]> {
  const u = uf.trim().toUpperCase();
  const c = cidade.trim();
  const l = logradouro.trim();
  if (!/^[A-Z]{2}$/.test(u)) throw new Error("UF inválida. Use a sigla com 2 letras (ex: SP).");
  if (c.length < 3) throw new Error("Informe a cidade com ao menos 3 letras.");
  if (l.length < 3) throw new Error("Informe o logradouro com ao menos 3 letras.");
  const chave = `${u}|${c.toLowerCase()}|${l.toLowerCase()}`;
  if (cacheEndereco.has(chave)) return cacheEndereco.get(chave)!;
  const url = `https://viacep.com.br/ws/${encodeURIComponent(u)}/${encodeURIComponent(c)}/${encodeURIComponent(l)}/json/`;
  let res: Response;
  try {
    res = await fetch(url);
  } catch {
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
  const lista = dados as EnderecoViaCep[];
  cacheEndereco.set(chave, lista);
  for (const e of lista) {
    const nc = normalizaCep(e.cep);
    if (nc.length === 8) cacheCep.set(nc, e);
  }
  return lista;
}

export async function buscarSugestoesCep(_prefixo: string): Promise<EnderecoViaCep[]> {
  return [];
}
