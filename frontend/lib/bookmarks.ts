import type { FeedEntrada } from "./api";

/**
 * "Salvar para ler depois" — inteiramente local (localStorage), sem
 * endpoint de backend dedicado. Guarda uma cópia leve da entrada do feed
 * para que a lista de salvos possa ser exibida sem depender de paginação
 * ou filtros do feed ao vivo.
 */

const CHAVE_SALVOS = "portal_noticias_salvos";

export function chaveDoSalvo(entrada: Pick<FeedEntrada, "tipo" | "id">): string {
  return `${entrada.tipo}-${entrada.id}`;
}

function lerSalvos(): FeedEntrada[] {
  if (typeof window === "undefined") return [];
  try {
    const bruto = window.localStorage.getItem(CHAVE_SALVOS);
    if (!bruto) return [];
    const dados = JSON.parse(bruto) as unknown;
    return Array.isArray(dados) ? (dados as FeedEntrada[]) : [];
  } catch {
    return [];
  }
}

function salvarLista(itens: FeedEntrada[]): void {
  try {
    window.localStorage.setItem(CHAVE_SALVOS, JSON.stringify(itens));
  } catch {
    // localStorage indisponível (ex.: modo privado) — o salvo só dura a sessão atual.
  }
}

export function obterSalvos(): FeedEntrada[] {
  return lerSalvos();
}

export function estaSalvo(entrada: Pick<FeedEntrada, "tipo" | "id">): boolean {
  const chave = chaveDoSalvo(entrada);
  return lerSalvos().some((item) => chaveDoSalvo(item) === chave);
}

/** Alterna salvo/não-salvo e devolve o novo estado. */
export function alternarSalvo(entrada: FeedEntrada): boolean {
  const chave = chaveDoSalvo(entrada);
  const atuais = lerSalvos();
  const jaSalvo = atuais.some((item) => chaveDoSalvo(item) === chave);
  if (jaSalvo) {
    salvarLista(atuais.filter((item) => chaveDoSalvo(item) !== chave));
    return false;
  }
  salvarLista([entrada, ...atuais]);
  return true;
}
