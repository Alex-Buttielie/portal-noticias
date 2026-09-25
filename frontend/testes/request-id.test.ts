/**
 * Testes da normalização de `X-Request-ID` (critérios 1, 2, 3, 28).
 *
 * O contrato com o backend é literalmente o mesmo conjunto de regras
 * (`backend/config/middleware.py::normalizar_request_id`), então o teste é
 * escrito do lado do CONTRATO, não da implementação: se um dia alguém "melhorar"
 * uma das regras aqui, este arquivo precisa mudar junto, e é essa colisão que
 * ele provoca.
 */

import { describe, expect, it } from "vitest";
import {
  caminhoSeguro,
  gerarRequestId,
  MAX_REQUEST_ID_LENGTH,
  normalizarRequestId,
} from "../lib/observabilidade";

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe("gerarRequestId", () => {
  it("devolve um UUID v4 canônico", () => {
    expect(gerarRequestId()).toMatch(UUID_V4);
  });

  it("não repete em mil puxadas", () => {
    const vistos = new Set<string>();
    for (let i = 0; i < 1000; i += 1) vistos.add(gerarRequestId());
    expect(vistos.size).toBe(1000);
  });

  it("respeita o teto de comprimento do backend (64)", () => {
    for (let i = 0; i < 50; i += 1) {
      expect(gerarRequestId().length).toBeLessThanOrEqual(MAX_REQUEST_ID_LENGTH);
    }
  });

  it("não usa Math.random (o degrau final é contador monotônico)", () => {
    // Sem WebCrypto o valor tem que continuar sendo único no processo: é o
    // índice unique de `EventoBusca.request_id` que depende disso.
    const original = globalThis.crypto;
    try {
      Object.defineProperty(globalThis, "crypto", { value: undefined, configurable: true });
      const a = gerarRequestId();
      const b = gerarRequestId();
      expect(a).not.toBe(b);
    } finally {
      Object.defineProperty(globalThis, "crypto", { value: original, configurable: true });
    }
  });
});

describe("normalizarRequestId", () => {
  it("preserva um id válido", () => {
    const id = "b1-proxy-check-1";
    expect(normalizarRequestId(id)).toBe(id);
  });

  it("preserva um UUID vindo do Django", () => {
    const id = "4da289fc-8a8a-41de-b56b-e25c091bea62";
    expect(normalizarRequestId(id)).toBe(id);
  });

  it("substitui por UUID novo quando ausente, vazio ou sentinel '-'", () => {
    for (const entrada of [null, undefined, "", "   ", "-"]) {
      expect(normalizarRequestId(entrada as string | null)).toMatch(UUID_V4);
    }
  });

  it("SUBSTITUI (não trunca) id longo demais — truncar colide no índice unique", () => {
    const longo = "x".repeat(MAX_REQUEST_ID_LENGTH + 1);
    const resultado = normalizarRequestId(longo);
    expect(resultado).toMatch(UUID_V4);
    expect(resultado).not.toContain("x");
  });

  it("aceita exatamente o limite", () => {
    const noLimite = "y".repeat(MAX_REQUEST_ID_LENGTH);
    expect(normalizarRequestId(noLimite)).toBe(noLimite);
  });

  it("substitui por caractere de controle, interno ou nas bordas", () => {
    // TAB/LF no MEIO: `trim()` os removeria das bordas, entao a
    // validacao precisa ser do valor BRUTO, como no backend.
    const entradas = [
      "abc\u0000def",
      "abc\ndef",
      "abc\tdef",
      "abc\u001bdef",
      "abc\u007fdef",
      "abc\u009fdef",
      " abc\u0007",
    ];
    for (const entrada of entradas) {
      expect(normalizarRequestId(entrada)).toMatch(UUID_V4);
    }
  });

  it("apara espaço nas bordas mas preserva o miolo", () => {
    expect(normalizarRequestId("  req-1  ")).toBe("req-1");
    expect(normalizarRequestId("req 1")).toBe("req 1");
  });

  it("nunca devolve o sentinel '-' nem string vazia", () => {
    for (const entrada of ["-", "", "  ", "\t", "a\u0000b", "x".repeat(200)]) {
      const saida = normalizarRequestId(entrada);
      expect(saida).not.toBe("-");
      expect(saida.length).toBeGreaterThan(0);
    }
  });
});

describe("caminhoSeguro", () => {
  it("remove query string, fragment e userinfo", () => {
    expect(caminhoSeguro("/buscar?q=segredo+de+busca")).toBe("/buscar");
    expect(caminhoSeguro("/noticia#secao")).toBe("/noticia");
    expect(caminhoSeguro("https://user:senha@portal.ex/noticia?x=1")).toBe(
      "https://portal.ex/noticia"
    );
  });

  it("preserva o path e trunca com marcador de elipse", () => {
    const longo = `/${"a".repeat(400)}`;
    const saida = caminhoSeguro(longo, 20);
    expect(saida.length).toBeLessThanOrEqual(20);
    expect(saida.endsWith("…")).toBe(true);
  });
});
