/**
 * Identidade visual por categoria — como não há imagens reais vindas do
 * backend (`FeedEntrada` não tem campo de foto), cada categoria ganha uma
 * cor de destaque e um emoji fixos. Dá ao feed uma "textura" visual e ajuda
 * o leitor a escanear a página por assunto, no lugar de um mar de cartões
 * idênticos em cinza.
 */

export interface VisualCategoria {
  cor: string;
  gradiente: string;
  emoji: string;
}

const MAPA_CATEGORIAS: Record<string, VisualCategoria> = {
  política: { cor: "#0f0f0f", gradiente: "linear-gradient(180deg, #0f0f0f 0%, #2e2a26 100%)", emoji: "●" },
  economia: { cor: "#57534e", gradiente: "linear-gradient(180deg, #1c1917 0%, #44403c 100%)", emoji: "●" },
  esportes: { cor: "#78716c", gradiente: "linear-gradient(180deg, #1c1917 0%, #57534e 100%)", emoji: "●" },
  tecnologia: { cor: "#44403c", gradiente: "linear-gradient(180deg, #0f0f0f 0%, #37302b 100%)", emoji: "●" },
  saúde: { cor: "#57534e", gradiente: "linear-gradient(180deg, #1c1917 0%, #3a3530 100%)", emoji: "●" },
  saude: { cor: "#57534e", gradiente: "linear-gradient(180deg, #1c1917 0%, #3a3530 100%)", emoji: "●" },
  cultura: { cor: "#44403c", gradiente: "linear-gradient(180deg, #0f0f0f 0%, #2e2a26 100%)", emoji: "●" },
  cidades: { cor: "#78716c", gradiente: "linear-gradient(180deg, #1c1917 0%, #44403c 100%)", emoji: "●" },
  mundo: { cor: "#0f0f0f", gradiente: "linear-gradient(180deg, #0f0f0f 0%, #2e2a26 100%)", emoji: "●" },
  ciência: { cor: "#44403c", gradiente: "linear-gradient(180deg, #1c1917 0%, #37302b 100%)", emoji: "●" },
  ciencia: { cor: "#44403c", gradiente: "linear-gradient(180deg, #1c1917 0%, #37302b 100%)", emoji: "●" },
};

const CORES_RESERVA = ["#78716c", "#a8a29e", "#57534e", "#44403c"];

function hashTexto(texto: string): number {
  let hash = 0;
  for (let i = 0; i < texto.length; i++) {
    hash = (hash * 31 + texto.charCodeAt(i)) >>> 0;
  }
  return hash;
}

export function obterVisualCategoria(categoria: string): VisualCategoria {
  const chave = categoria.trim().toLowerCase();
  if (MAPA_CATEGORIAS[chave]) return MAPA_CATEGORIAS[chave];
  if (!chave) return { cor: CORES_RESERVA[0], gradiente: CORES_RESERVA[0], emoji: "📰" };
  const cor = CORES_RESERVA[hashTexto(chave) % CORES_RESERVA.length];
  return { cor, gradiente: cor, emoji: "📰" };
}
