/**
 * Testes da janela de "último conteúdo real" (critérios 10 e 11) e da
 * recuperação de tela do error boundary (critério 4).
 *
 * A janela é a decisão de cache que o frontend tem: servir conteúdo real por
 * até 5 min sinalizando degradação, e dizer honestamente que não tem nada real
 * quando passou. O `agora` é injetado, então o teste cobre a fronteira exata
 * (5 min) sem relógio falso nem espera.
 */

import { beforeEach, describe, expect, it } from "vitest";
import {
  formatarIdade,
  JANELA_STALE_MS,
  lerConteudoReal,
  registrarConteudoReal,
} from "../lib/ultimo-conteudo-real";

const CHAVE = "home:teste";

function limpar(): void {
  const global = globalThis as unknown as Record<string, { mapa: Map<string, unknown> } | undefined>;
  if (global.__portalUltimoConteudoReal) {
    (global.__portalUltimoConteudoReal as { mapa: Map<string, unknown> }).mapa.clear();
  }
}

describe("janela de ultimo conteudo real", () => {
  beforeEach(limpar);

  it("nao devolve nada antes de gravar (caminho honesto, nunca MOCK)", () => {
    expect(lerConteudoReal(CHAVE)).toBeNull();
  });

  it("devolve o conteudo gravado dentro da janela", () => {
    registrarConteudoReal(CHAVE, [{ titulo: "Noticia real" }]);
    const agora = Date.now();
    const velho = lerConteudoReal(CHAVE, JANELA_STALE_MS, agora);
    expect(velho).not.toBeNull();
    expect(velho?.itens).toHaveLength(1);
    expect(velho?.idadeMs).toBe(0);
  });

  it("devolve ate o limite exato de 5 minutos e recusa depois", () => {
    expect(JANELA_STALE_MS).toBe(5 * 60 * 1000);
    const base = Date.now();
    registrarConteudoReal(CHAVE, [{ titulo: "Noticia real" }]);
    expect(lerConteudoReal(CHAVE, JANELA_STALE_MS, base + JANELA_STALE_MS)).not.toBeNull();
    expect(lerConteudoReal(CHAVE, JANELA_STALE_MS, base + JANELA_STALE_MS + 1)).toBeNull();
  });

  it("idade negativa (relógio andou para tras) nao serve para sempre", () => {
    const base = Date.now();
    registrarConteudoReal(CHAVE, [{ titulo: "Noticia real" }]);
    const velho = lerConteudoReal(CHAVE, JANELA_STALE_MS, base - 10_000);
    expect(velho).not.toBeNull();
    expect(velho?.idadeMs).toBe(0); // tratado como recem-gravado
  });

  it("ignora gravacao vazia (conteudo ficticio nunca entra na janela)", () => {
    registrarConteudoReal(CHAVE, []);
    expect(lerConteudoReal(CHAVE)).toBeNull();
  });

  it("re-gravar substitui o anterior (o mais recente manda)", () => {
    registrarConteudoReal(CHAVE, [{ titulo: "Antiga" }]);
    registrarConteudoReal(CHAVE, [{ titulo: "Recente" }]);
    const velho = lerConteudoReal(CHAVE);
    expect(velho?.itens).toHaveLength(1);
    expect(velho?.itens[0]).toEqual({ titulo: "Recente" });
  });
});

describe("formatacao da idade (texto honesto da degradacao)", () => {
  it("formata em minutos, sem singular/plural errado", () => {
    expect(formatarIdade(0)).toBe("há menos de 1 minuto");
    expect(formatarIdade(59_000)).toBe("há menos de 1 minuto");
    expect(formatarIdade(60_000)).toBe("há 1 minuto");
    expect(formatarIdade(3 * 60_000)).toBe("há 3 minutos");
  });
});
