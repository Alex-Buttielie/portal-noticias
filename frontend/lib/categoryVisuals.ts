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
  política: { cor: "#b5473a", gradiente: "linear-gradient(135deg, #b5473a, #7a2e26)", emoji: "🏛️" },
  economia: { cor: "#1b7f5f", gradiente: "linear-gradient(135deg, #1b7f5f, #0f4f3b)", emoji: "📈" },
  esportes: { cor: "#e08a1e", gradiente: "linear-gradient(135deg, #e08a1e, #a85f0f)", emoji: "⚽" },
  tecnologia: { cor: "#3a6fd8", gradiente: "linear-gradient(135deg, #3a6fd8, #23458f)", emoji: "💻" },
  saúde: { cor: "#1f9e8f", gradiente: "linear-gradient(135deg, #1f9e8f, #146a60)", emoji: "🩺" },
  saude: { cor: "#1f9e8f", gradiente: "linear-gradient(135deg, #1f9e8f, #146a60)", emoji: "🩺" },
  cultura: { cor: "#9b4fc9", gradiente: "linear-gradient(135deg, #9b4fc9, #6b2f8f)", emoji: "🎭" },
  cidades: { cor: "#c9612f", gradiente: "linear-gradient(135deg, #c9612f, #8f4520)", emoji: "🏙️" },
  mundo: { cor: "#2f8fc9", gradiente: "linear-gradient(135deg, #2f8fc9, #1f5f8f)", emoji: "🌍" },
  ciência: { cor: "#4f7fd8", gradiente: "linear-gradient(135deg, #4f7fd8, #2f4f9f)", emoji: "🔬" },
  ciencia: { cor: "#4f7fd8", gradiente: "linear-gradient(135deg, #4f7fd8, #2f4f9f)", emoji: "🔬" },
};

const CORES_RESERVA = ["#6b7280", "#8a6b4f", "#5f7a8f", "#7a5f8f"];

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
