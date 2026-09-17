export const FONTES_CATALOGO = [
  "G1",
  "UOL",
  "CNN Brasil",
  "Folha",
  "Estadão",
  "R7",
  "Terra",
  "BBC Brasil",
] as const;

const CHAVE = "brd.minhas-fontes.v1";

function ler(): string[] {
  try {
    const raw = localStorage.getItem(CHAVE);
    if (!raw) return [...FONTES_CATALOGO.slice(0, 4)];
    const arr = JSON.parse(raw) as unknown;
    if (Array.isArray(arr)) return arr.filter((x): x is string => typeof x === "string");
  } catch {}
  return [...FONTES_CATALOGO.slice(0, 4)];
}

function gravar(lista: string[]) {
  try {
    localStorage.setItem(CHAVE, JSON.stringify(lista));
  } catch {}
}

export function obterMinhasFontes(): string[] {
  return ler();
}

export function segueFonte(nome: string): boolean {
  return ler().some((f) => f.toLowerCase() === nome.toLowerCase());
}

export function alternarFonte(nome: string): string[] {
  const atual = ler();
  const nomeLimpo = nome.trim();
  if (!nomeLimpo) return atual;
  const idx = atual.findIndex((f) => f.toLowerCase() === nomeLimpo.toLowerCase());
  const nova = idx >= 0 ? atual.filter((_, i) => i !== idx) : [...atual, nomeLimpo];
  gravar(nova);
  return nova;
}

export function definirMinhasFontes(lista: string[]): string[] {
  const limpa = Array.from(new Set(lista.map((s) => s.trim()).filter(Boolean)));
  gravar(limpa);
  return limpa;
}
