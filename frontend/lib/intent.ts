/**
 * Sinais de intenção do leitor, capturados no cliente (localStorage) para
 * alimentar o design orientado à intenção do feed: nunca reordena o feed
 * silenciosamente (a paginação vem do backend), só usa os sinais para
 * destacar cartões relevantes e sugerir um filtro — sempre de forma
 * visível e descartável pelo usuário.
 */

const CHAVE_INTERESSES = "portal_noticias_intencao_categorias";
const LIMIAR_SUGESTAO = 3;

type ContagemCategorias = Record<string, number>;

function lerContagens(): ContagemCategorias {
  if (typeof window === "undefined") return {};
  try {
    const bruto = window.localStorage.getItem(CHAVE_INTERESSES);
    if (!bruto) return {};
    const dados = JSON.parse(bruto) as unknown;
    if (dados && typeof dados === "object") return dados as ContagemCategorias;
    return {};
  } catch {
    return {};
  }
}

function salvarContagens(contagens: ContagemCategorias): void {
  try {
    window.localStorage.setItem(CHAVE_INTERESSES, JSON.stringify(contagens));
  } catch {
    // localStorage indisponível (ex.: modo privado) — sinal de intenção fica só na sessão atual.
  }
}

/** Registra que o leitor abriu uma notícia de determinada categoria. */
export function registrarLeitura(categoria: string): void {
  if (!categoria) return;
  const contagens = lerContagens();
  contagens[categoria] = (contagens[categoria] || 0) + 1;
  salvarContagens(contagens);
}

export interface CategoriaPreferida {
  categoria: string;
  leituras: number;
}

/** Categoria com mais leituras registradas, se houver sinal suficiente. */
export function obterCategoriaPreferida(): CategoriaPreferida | null {
  const contagens = lerContagens();
  const entradas = Object.entries(contagens) as [string, number][];
  if (entradas.length === 0) return null;
  const [categoria, leituras] = entradas.reduce((maior, atual) =>
    atual[1] > maior[1] ? atual : maior
  );
  if (leituras < LIMIAR_SUGESTAO) return null;
  return { categoria, leituras };
}

/** Quantas leituras já foram registradas para uma categoria específica. */
export function obterLeiturasDaCategoria(categoria: string): number {
  if (!categoria) return 0;
  return lerContagens()[categoria] || 0;
}
