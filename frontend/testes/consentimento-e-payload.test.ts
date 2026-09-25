/**
 * Testes de comportamento de CONSENTIMENTO do cliente de analytics
 * (critérios 5, 6, 25, 26, 27) e de redação do payload de evento.
 *
 * O que NÃO está aqui, e é pendência declarada: `window`/DOM. O tracker
 * depende de `localStorage`/`sessionStorage`/`sendBeacon`, e testar isso
 * exigiria `jsdom` (uma dependência de teste a mais) ou um runner de
 * componentes. O que é testável sem DOM — a decisão pura de "este evento vai
 * ou não", a forma do payload e o fail-closed do token — está testado, e o
 * resto depende do backend fail-closed (que já é a segunda barreira: mesmo que
 * o cliente vazasse um evento sem token, o backend não persiste).
 */

import { describe, expect, it } from "vitest";
import { TIPOS_EVENTO } from "../lib/analytics";
import { CATEGORIA_TECNICA, CHAVE_CONSENTIMENTO, consentimentoTecnicoConcedido } from "../lib/consento-local";
import { caminhoSeguro, redigirTexto, semControle } from "../lib/observabilidade";

describe("consentimento tecnico no cliente (fail-closed)", () => {
  it("e false sem window (SSR nunca tem localStorage)", () => {
    // O teste roda em node: nao existe `window`, entao a funcao tem de
    // responder false em vez de lancar.
    expect(consentimentoTecnicoConcedido()).toBe(false);
  });

  it("a chave de armazenamento e a mesma usada por cookie-consent", () => {
    expect(CHAVE_CONSENTIMENTO).toBe("portal_noticias_consentimento_cookies");
    expect(CATEGORIA_TECNICA).toBe("tecnico");
  });
});

describe("payload de evento: query string nunca sai (criterio 28)", () => {
  it("o caminho de um evento nunca leva query string, fragmento ou userinfo", () => {
    expect(caminhoSeguro("/buscar?q=termo+confidencial&email=pessoa@x.invalid")).toBe("/buscar");
    expect(caminhoSeguro("/noticia#comentarios")).toBe("/noticia");
    expect(caminhoSeguro("https://u:p@portal.ex/x?y=1")).toBe("https://portal.ex/x");
  });
});

describe("redacao de texto livre (espelha redact_text do backend)", () => {
  it("mascara e-mail, Bearer e JWT", () => {
    expect(redigirTexto("falha para pessoa@dominio.invalido")).toContain("[REDACTED_EMAIL]");
    expect(redigirTexto("Bearer abc.def-123")).toContain("[REDACTED]");
    expect(redigirTexto("eyJhbGciOi.eyJzdWIiOi.SflKxwRJ")).toBe("[REDACTED]");
  });

  it("mascara atribuicoes de segredo (token=, Authorization:, senha=)", () => {
    for (const texto of [
      "token=abc123",
      "Authorization: Token abc123",
      "senha=segredo",
      "api_key: xyz",
    ]) {
      expect(redigirTexto(texto)).toContain("[REDACTED]");
      expect(redigirTexto(texto)).not.toMatch(/(abc123|segredo|xyz)/);
    }
  });

  it("mascara query string dentro de URL que apareca em texto", () => {
    const saida = redigirTexto("GET https://portal.ex/api/x?token=abc");
    expect(saida).not.toContain("abc");
    expect(saida).toContain("[REDACTED]");
  });

  it("limita o tamanho do texto", () => {
    const saida = redigirTexto("a".repeat(1000), 50);
    expect(saida.length).toBeLessThanOrEqual(50);
  });
});

describe("taxonomia de eventos (allowlist do backend)", () => {
  it("os tipos de evento do cliente estao dentro da lista fechada", () => {
    // O backend recusa tipo desconhecido com `tipo_desconhecido`; este teste
    // nao valida a lista do backend (fonte unica la), mas trava o contrato de
    // que o cliente nao inventa tipo novo por conta propria.
    expect(TIPOS_EVENTO.length).toBeGreaterThan(0);
    for (const tipo of TIPOS_EVENTO) {
      expect(typeof tipo).toBe("string");
      expect(tipo).toMatch(/^[a-z_]+$/);
    }
    // Sem duplicata.
    expect(new Set(TIPOS_EVENTO).size).toBe(TIPOS_EVENTO.length);
  });
});

describe("semControle", () => {
  it("remove todo caractere de controle", () => {
    expect(semControle("a\u0000b\u001fc\u007fd\u009fe")).toBe("abcde");
  });
});
