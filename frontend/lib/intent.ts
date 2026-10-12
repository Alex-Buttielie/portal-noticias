/**
 * Sinais de intenção do leitor, capturados no cliente (localStorage) para
 * alimentar o design orientado à intenção do feed: nunca reordena o feed
 * silenciosamente (a paginação vem do backend), só usa os sinais para
 * destacar cartões relevantes e sugerir um filtro — sempre de forma
 * visível e descartável pelo usuário.
 */

const CHAVE_INTERESSES = "portal_noticias_intencao_categorias";
const LIMIAR_SUGESTAO = 3;
// Meia-vida do interesse: 10 dias sem ler uma categoria e o peso dela cai
// pela metade. Sem isso, um binge antigo em "esportes" dominava o "Para
// você" para sempre, mesmo que o leitor tenha migrado de interesse — o
// feed parava de parecer vivo/atual.
const MEIA_VIDA_DIAS = 10;

interface RegistroCategoria {
  n: number;
  t: number; // epoch ms da leitura mais recente
}

type ContagemCategorias = Record<string, number>;
type RegistrosCategorias = Record<string, RegistroCategoria>;

function paraRegistro(valor: unknown, agora: number): RegistroCategoria | null {
  if (typeof valor === "number") return { n: valor, t: agora }; // formato antigo (sem timestamp)
  if (valor && typeof valor === "object" && typeof (valor as RegistroCategoria).n === "number") {
    const r = valor as RegistroCategoria;
    return { n: r.n, t: typeof r.t === "number" ? r.t : agora };
  }
  return null;
}

function lerRegistros(): RegistrosCategorias {
  if (typeof window === "undefined") return {};
  try {
    const bruto = window.localStorage.getItem(CHAVE_INTERESSES);
    if (!bruto) return {};
    const dados = JSON.parse(bruto) as unknown;
    if (!dados || typeof dados !== "object") return {};
    const agora = Date.now();
    const registros: RegistrosCategorias = {};
    for (const [categoria, valor] of Object.entries(dados as Record<string, unknown>)) {
      const r = paraRegistro(valor, agora);
      if (r) registros[categoria] = r;
    }
    return registros;
  } catch {
    return {};
  }
}

function salvarRegistros(registros: RegistrosCategorias): void {
  try {
    window.localStorage.setItem(CHAVE_INTERESSES, JSON.stringify(registros));
  } catch {
    // localStorage indisponível (ex.: modo privado) — sinal de intenção fica só na sessão atual.
  }
}

/** Peso decaído pelo tempo desde a última leitura (meia-vida exponencial). */
function pesoDecaido(registro: RegistroCategoria, agora: number): number {
  const diasDesde = Math.max(0, (agora - registro.t) / 86_400_000);
  return registro.n * Math.pow(0.5, diasDesde / MEIA_VIDA_DIAS);
}

/** Registra que o leitor abriu uma notícia de determinada categoria. */
export function registrarLeitura(categoria: string): void {
  if (!categoria) return;
  const registros = lerRegistros();
  const atual = registros[categoria];
  registros[categoria] = { n: (atual?.n || 0) + 1, t: Date.now() };
  salvarRegistros(registros);
}

export interface CategoriaPreferida {
  categoria: string;
  leituras: number;
}

/** Categoria com mais leituras registradas (ponderadas por recência), se houver sinal suficiente. */
export function obterCategoriaPreferida(): CategoriaPreferida | null {
  const contagens = obterTodasLeituras();
  const entradas = Object.entries(contagens) as [string, number][];
  if (entradas.length === 0) return null;
  const [categoria, leituras] = entradas.reduce((maior, atual) =>
    atual[1] > maior[1] ? atual : maior
  );
  if (leituras < LIMIAR_SUGESTAO) return null;
  return { categoria, leituras };
}

/** Quantas leituras (ponderadas por recência) já foram registradas para uma categoria específica. */
export function obterLeiturasDaCategoria(categoria: string): number {
  if (!categoria) return 0;
  return obterTodasLeituras()[categoria] || 0;
}

/** Contagem por categoria ponderada por recência (para ranqueamento por gosto). */
export function obterTodasLeituras(): Record<string, number> {
  const agora = Date.now();
  const registros = lerRegistros();
  const pesos: ContagemCategorias = {};
  for (const [categoria, registro] of Object.entries(registros)) {
    pesos[categoria] = pesoDecaido(registro, agora);
  }
  return pesos;
}
