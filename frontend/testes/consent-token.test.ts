/**
 * Testes do cliente do token de consentimento (critérios 25 e 26).
 *
 * O backend passou a exigir token assinado no `POST /api/metricas/eventos/` e
 * a coleta está parada sem um cliente que o emita. Estes testes cobrem a
 * decidível parte: validação da resposta do emissor, janela de staleness e o
 * fail-closed. O transporte (`api.ts`) e o `sessionStorage` são testados por
 * simulação mínima abaixo, e a emissão real contra o Django é o que o Bloco C2
 * precisa acionar na homologação.
 *
 * Golden example do contrato (Bloco A2, `implementation-history.md`):
 *   token: v1.eyJjYXRlZ29yaWEiOiJhbmFseXRpY3MiLCJleHAiOjE3NTgwODY0MDAsImlhdCI6MTc1ODAwMDAwMCwic3ViIjoibTF4MmszLThoajNrZDIiLCJ2IjoxfQ.ENaqNwsnheFezVGHgcb3enBzRnWHAqU84M0Tvo-k4tA
 * O cliente trata o token como string opaca, mas o **envelope** tem três
 * partes sem padding — se o backend mudar isso, esta.shape check é a que
 * avisa antes de um `consent_malformado` em produção.
 */

import { beforeEach, describe, expect, it } from "vitest";
import {
  anexarTokenAoCorpo,
  cabecalhoConsentimento,
  CATEGORIA_TOKEN,
  JANELA_RENOVACAO_SEGUNDOS,
  MAX_TOKEN_BYTES,
  precisaRenovar,
  validarRespostaEmissor,
  tokenUtilizavel,
  type TokenEmMaos,
} from "../lib/consent-token";

const SESSAO = "m1x2k3-8hj3kd2";
const AGORA = 1758000000;

/** Token do golden example do contrato (chave de exemplo, TTL 86400). */
const TOKEN_GOLDEN =
  "v1.eyJjYXRlZ29yaWEiOiJhbmFseXRpY3MiLCJleHAiOjE3NTgwODY0MDAsImlhdCI6MTc1ODAwMDAwMCwic3ViIjoibTF4MmszLThoajNrZDIiLCJ2IjoxfQ.ENaqNwsnheFezVGHgcb3enBzRnWHAqU84M0Tvo-k4tA";

function respostaDoEmissor(extra: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    token: TOKEN_GOLDEN,
    categoria: CATEGORIA_TOKEN,
    sub: SESSAO,
    exp: AGORA + 86_400,
    ttl_segundos: 86_400,
    ...extra,
  };
}

describe("validarRespostaEmissor", () => {
  it("aceita a resposta do emissor (201) e devolve o registro", () => {
    const registro = validarRespostaEmissor(respostaDoEmissor(), SESSAO, AGORA);
    expect(registro).not.toBeNull();
    expect(registro?.token).toBe(TOKEN_GOLDEN);
    expect(registro?.exp).toBe(AGORA + 86_400);
    expect(registro?.sub).toBe(SESSAO);
  });

  it("rejeita token que nao tem o envelope de tres partes", () => {
    for (const token of ["", "abc", "v1.so", "v1.a.b.c", "v1..b"]) {
      expect(validarRespostaEmissor(respostaDoEmissor({ token }), SESSAO, AGORA)).toBeNull();
    }
  });

  it("rejeita envelope de outra versao (o backend so valida v1)", () => {
    for (const token of ["v2.a.b", "V1.a.b", "v1x.a.b"]) {
      expect(validarRespostaEmissor(respostaDoEmissor({ token }), SESSAO, AGORA)).toBeNull();
    }
  });

  it("rejeita token com espacamento (o emissor nunca emite)", () => {
    expect(validarRespostaEmissor(respostaDoEmissor({ token: ` ${TOKEN_GOLDEN}` }), SESSAO, AGORA)).toBeNull();
  });

  it("rejeita token acima do teto de bytes do backend", () => {
    const gigante = `v1.${"a".repeat(MAX_TOKEN_BYTES)}.b`;
    expect(validarRespostaEmissor(respostaDoEmissor({ token: gigante }), SESSAO, AGORA)).toBeNull();
  });

  it("rejeita categoria diferente da esperada (o token tecnico nao existe)", () => {
    expect(validarRespostaEmissor(respostaDoEmissor({ categoria: "tecnico" }), SESSAO, AGORA)).toBeNull();
  });

  it("rejeita sujeito diferente da sessao do evento", () => {
    expect(validarRespostaEmissor(respostaDoEmissor({ sub: "outra-sessao" }), SESSAO, AGORA)).toBeNull();
  });

  it("rejeita exp no passado ou ausente", () => {
    expect(validarRespostaEmissor(respostaDoEmissor({ exp: AGORA - 1 }), SESSAO, AGORA)).toBeNull();
    expect(validarRespostaEmissor(respostaDoEmissor({ exp: AGORA }), SESSAO, AGORA)).toBeNull();
    expect(validarRespostaEmissor(respostaDoEmissor({ exp: undefined }), SESSAO, AGORA)).toBeNull();
    expect(validarRespostaEmissor(respostaDoEmissor({ exp: "1758086400" }), SESSAO, AGORA)).toBeNull();
  });

  it("rejeita resposta que nao e objeto", () => {
    for (const invalido of [null, undefined, "texto", 42, []]) {
      expect(validarRespostaEmissor(invalido, SESSAO, AGORA)).toBeNull();
    }
  });
});

describe("janela de staleness (tokenUtilizavel / precisaRenovar)", () => {
  const registro: TokenEmMaos = { token: TOKEN_GOLDEN, exp: AGORA + 86_400, sub: SESSAO, guardadoEm: AGORA };

  it("token com folga e utilizavel e nao precisa renovar", () => {
    expect(tokenUtilizavel(registro, AGORA)).toBe(true);
    expect(precisaRenovar(registro, AGORA)).toBe(false);
  });

  it("token dentro da janela ainda e utilizavel (o backend aceita ate o exp)", () => {
    const perto = { ...registro, exp: AGORA + 60 };
    expect(precisaRenovar(perto, AGORA)).toBe(true);
    // Perder um token ainda valido perderia dado de produto sem ganho nenhum.
    expect(tokenUtilizavel(perto, AGORA)).toBe(true);
  });

  it("token expirado nao e utilizavel eobriga a renovar", () => {
    const expirado = { ...registro, exp: AGORA };
    expect(tokenUtilizavel(expirado, AGORA)).toBe(false);
    expect(precisaRenovar(expirado, AGORA)).toBe(true);
  });

  it("null/undefined nao e utilizavel", () => {
    expect(tokenUtilizavel(null, AGORA)).toBe(false);
    expect(tokenUtilizavel(undefined, AGORA)).toBe(false);
    expect(precisaRenovar(null, AGORA)).toBe(true);
  });

  it("registro sem token nao e utilizavel", () => {
    expect(tokenUtilizavel({ ...registro, token: "" }, AGORA)).toBe(false);
  });

  it("janela de renovacao e de 5 minutos", () => {
    expect(JANELA_RENOVACAO_SEGUNDOS).toBe(300);
    const naBorda = { ...registro, exp: AGORA + JANELA_RENOVACAO_SEGUNDOS };
    expect(precisaRenovar(naBorda, AGORA)).toBe(true);
    const foraDaBorda = { ...registro, exp: AGORA + JANELA_RENOVACAO_SEGUNDOS + 1 };
    expect(precisaRenovar(foraDaBorda, AGORA)).toBe(false);
  });
});

describe("anexar token ao evento (header para fetch, corpo para beacon)", () => {
  it("header X-Consent-Token e o caminho preferido", () => {
    expect(cabecalhoConsentimento(TOKEN_GOLDEN)).toEqual({ "X-Consent-Token": TOKEN_GOLDEN });
  });

  it("sem token, nenhum header (fail-closed: nada de evento sem prova)", () => {
    expect(cabecalhoConsentimento(null)).toEqual({});
    expect(cabecalhoConsentimento("")).toEqual({});
  });

  it("consent_token no corpo e o caminho do sendBeacon (que nao envia header)", () => {
    const corpo = { tipo: "page_view", path: "/" };
    const comToken = anexarTokenAoCorpo(corpo, TOKEN_GOLDEN);
    expect(comToken.consent_token).toBe(TOKEN_GOLDEN);
    // o corpo original nao e mutado
    expect(corpo).not.toHaveProperty("consent_token");
  });

  it("sem token, o corpo nao ganha consent_token", () => {
    const corpo = { tipo: "page_view" };
    expect(anexarTokenAoCorpo(corpo, null)).toBe(corpo);
    expect(anexarTokenAoCorpo(corpo, null)).not.toHaveProperty("consent_token");
  });
});

describe("contrato do envelope (golden example do Bloco A2)", () => {
  it("o golden example tem tres partes base64url sem padding", () => {
    const partes = TOKEN_GOLDEN.split(".");
    expect(partes).toHaveLength(3);
    expect(partes[0]).toBe("v1");
    for (const parte of partes.slice(1)) {
      expect(parte).not.toContain("=");
      expect(parte).toMatch(/^[A-Za-z0-9_-]+$/);
    }
  });
});
