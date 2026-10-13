import { obterFontesSeguidas, seguirFonte, deixarDeSeguirFonte } from "./api";

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

/**
 * `token`: quando logado, a mudança também é persistida na conta (fire-
 * and-forget — a UI já respondeu com o `localStorage` antes da rede
 * voltar; falha de rede nunca bloqueia o toggle local). Sem token, fica
 * só no dispositivo, como sempre foi.
 */
export function alternarFonte(nome: string, token?: string | null): string[] {
  const atual = ler();
  const nomeLimpo = nome.trim();
  if (!nomeLimpo) return atual;
  const idx = atual.findIndex((f) => f.toLowerCase() === nomeLimpo.toLowerCase());
  const passouASeguir = idx < 0;
  const nova = idx >= 0 ? atual.filter((_, i) => i !== idx) : [...atual, nomeLimpo];
  gravar(nova);
  if (token) {
    const chamada = passouASeguir ? seguirFonte(nomeLimpo, token) : deixarDeSeguirFonte(nomeLimpo, token);
    chamada.catch(() => {});
  }
  return nova;
}

export function definirMinhasFontes(lista: string[]): string[] {
  const limpa = Array.from(new Set(lista.map((s) => s.trim()).filter(Boolean)));
  gravar(limpa);
  return limpa;
}

/** Busca as fontes seguidas na conta (logada) e funde com o que já havia
 * no dispositivo (união — nunca perde o que o leitor já tinha marcado
 * localmente antes de logar). Chamar uma vez após login/hidratação. */
export async function sincronizarMinhasFontes(token: string): Promise<string[]> {
  try {
    const doServidor = await obterFontesSeguidas(token);
    const local = ler();
    const unidas = Array.from(new Set([...local, ...doServidor]));
    gravar(unidas);
    return unidas;
  } catch {
    return ler();
  }
}
