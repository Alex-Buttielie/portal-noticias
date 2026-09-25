/**
 * Janela de "último conteúdo real" (implementation-contract.md run
 * 20260925-1020-observabilidade, critérios 10 e 11).
 *
 * POR QUE ESTA CAMADA E NÃO O BACKEND: o comportamento exigido ("dados reais
 * por até 5 min, sinalizando degradação; 503 quando não há dado válido") tem
 * duas metades:
 *
 * 1. Servir o último conteúdo real por um prazo curto, sinalizando que está
 *    velho. Isso é cache stale-while-error, e o lugar natural é o ISR do Next:
 *    a página tem `revalidate` próprio e uma falha na revalidação não pode
 *    apagar o que já foi servido. O backend tem cache de feed com TTL próprio
 *    e não conhece a janela de revalidação da Home.
 * 2. Dizer "não tenho nada real" com honestidade. O backend é quem sabe se o
 *    feed está de pé; o frontend é quem decide o que mostrar quando não sabe.
 *
 * O FOLLOW-UP com o backend está registrado em `bloco-b1-notas.md`: header de
 * idade/`cached_at` no feed, 503 no próprio endpoint de feed, e isentar a
 * resposta degradada do `proxy_cache` do nginx. Nenhum dos três é implementável
 * aqui — `backend/feed/views.py` é WIP de outra run e o nginx é do bloco de
 * infra.
 *
 * ARMAZENAMENTO: memória do processo, via `globalThis` (sobrevive à duplicação
 * de módulo do `next dev` e é o mesmo objeto entre Server Components do mesmo
 * processo). Consequência assumida e documentada: a janela é por PROCESSO. Um
 * restart, ou o segundo worker de um pool com mais de um, começa sem histórico
 * e cai no caminho honesto (estado indisponível) em vez de inventar. O
 * portal de produção roda como processo único (PM2 + `output: standalone`), e
 * o limite de 5 min é curto o bastante para que "sem histórico" seja o estado
 * normal logo depois de um deploy.
 */

export const JANELA_STALE_MS = 5 * 60 * 1000;

interface Registro<T> {
  itens: T[];
  gravadoEm: number;
}

interface Armazenamento {
  mapa: Map<string, Registro<unknown>>;
}

const CHAVE = "__portalUltimoConteudoReal";

function armazenamento(): Armazenamento {
  const global = globalThis as unknown as Record<string, Armazenamento | undefined>;
  if (!global[CHAVE]) global[CHAVE] = { mapa: new Map() };
  return global[CHAVE] as Armazenamento;
}

/**
 * Teto de chaves. O mapa é por "rota de conteúdo" (home, categoria, arquivo...);
 * mesmo que alguém passe a registrar muitas, o crescimento é limitado.
 */
const MAX_CHAVES = 32;

export function registrarConteudoReal<T>(chave: string, itens: T[]): void {
  if (!chave || !Array.isArray(itens) || itens.length === 0) return;
  const { mapa } = armazenamento();
  mapa.delete(chave);
  mapa.set(chave, { itens, gravadoEm: Date.now() });
  while (mapa.size > MAX_CHAVES) {
    const maisAntigo = mapa.keys().next();
    if (maisAntigo.done) break;
    mapa.delete(maisAntigo.value);
  }
}

export interface ConteudoVelho<T> {
  itens: T[];
  idadeMs: number;
  gravadoEm: number;
}

/**
 * Devolve o último conteúdo real gravado, desde que ainda esteja dentro da
 * janela. `agora` é injetável para tornar a regra testável sem relógio falso.
 */
export function lerConteudoReal<T>(chave: string, janelaMs = JANELA_STALE_MS, agora = Date.now()): ConteudoVelho<T> | null {
  const registro = armazenamento().mapa.get(chave) as Registro<T> | undefined;
  if (!registro) return null;
  const idadeMs = agora - registro.gravadoEm;
  // Idade negativa (relógio andou para trás entre processos) não é motivo para
  // descartar dado real: trata como recém-gravado em vez de servir para sempre.
  if (idadeMs > janelaMs) return null;
  if (!registro.itens.length) return null;
  return { itens: registro.itens, idadeMs: Math.max(0, idadeMs), gravadoEm: registro.gravadoEm };
}

/** "há 3 min" / "agora há pouco", para o texto honesto da degradação. */
export function formatarIdade(idadeMs: number): string {
  const minutos = Math.floor(idadeMs / 60_000);
  if (minutos < 1) return "há menos de 1 minuto";
  if (minutos === 1) return "há 1 minuto";
  return `há ${minutos} minutos`;
}
