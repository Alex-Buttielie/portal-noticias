/**
 * A base que o SERVIDOR usa para falar com a API não pode depender do DNS
 * público.
 *
 * O DEFEITO (medido em 2026-10-08)
 * ===============================
 * `lib/api.ts` resolvia a base assim:
 *
 *     typeof window !== "undefined" && NODE_ENV === "production"
 *       ? ""                                        // navegador
 *       : process.env.NEXT_PUBLIC_API_BASE_URL      // servidor
 *
 * O `deploy.sh` grava `NEXT_PUBLIC_API_BASE_URL` como a **origem pública**
 * (`http://$HOST`). Funciona para o navegador, que sai pela internet. Não
 * funciona para o servidor: ele não sai para a internet, e `$HOST` não
 * resolve a partir da própria VPS enquanto o DNS não apontar para ela.
 *
 * MEDIDO em DEV e HOMOLOG (que rodam o código atual):
 *
 *   - o bundle do DEV continha `dev.portal-noticias.com.br` **543 vezes**;
 *   - `getent hosts dev.portal-noticias.com.br` na VPS: **não resolve**;
 *   - `fetch` para `http://127.0.0.1:5101/...` (o gunicorn real): **HTTP 200**;
 *   - `/categoria/*`, `/arquivo`, `/paginas/*`, `/buscar`: HTTP 200 com
 *     "Não foi possível carregar";
 *   - a home: HTTP 200 com 593 caracteres — esqueleto sem conteúdo.
 *
 * PROD não era afetado por rodar o código de 24/09.
 *
 * E o mais grave: `/paginas/<slug>` tinha um fallback que FABRICAVA conteúdo
 * quando a busca falhava (P0-08). Esse fallback estava **escondendo** este
 * defeito — a página parecia funcionar. Um estado de erro honesto expõe o
 * defeito que a fabricação escondia; foi exatamente assim que ele apareceu.
 *
 * POR QUE A VARIÁVEL DO SERVIDOR NÃO PODE SER `NEXT_PUBLIC_*`
 * =============================================================
 * O sufixo `PUBLIC_` faz o Next embutir o valor no bundle do **navegador**.
 * `http://127.0.0.1:5101` no cliente é um endereço que não existe na máquina
 * de quem lê o site — e vazaria a porta interna do gunicorn.
 *
 * `API_INTERNAL_URL` não tem o sufixo: o navegador não a vê, e
 * `lib/cep.ts`, `lib/regiao.ts` e `lib/ibge.ts` — que rodam no cliente e leem
 * `NEXT_PUBLIC_API_BASE_URL` de propósito — continuam com a origem pública.
 *
 * COMO ESTE TESTE MEDE
 * ====================
 * `API_BASE_URL` é uma `const` avaliada no import. Para medir cada ordem de
 * precedência é preciso importar o módulo com o ambiente já montado — daí o
 * cache-busting por query string, que força o Node a reavaliar o módulo.
 *
 * O que fica de fora, e é relevante: este teste prova a **precedência** da
 * escolha, não que a rede funciona. Que `http://127.0.0.1:5101` responde 200 é
 * medido na VPS, e o efeito nas páginas só aparece depois do deploy. Um teste
 * que validasse a segunda parte precisaria subir servidor e banco.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";

const RAIZ = path.resolve(import.meta.dirname, "..");
const MODULO_API = path.join(RAIZ, "lib", "api.ts");

/** Importa `lib/api.ts` com um ambiente montado e devolve `API_BASE_URL`. */
async function baseCom(amb) {
  const anterior = {};
  for (const k of ["API_INTERNAL_URL", "NEXT_PUBLIC_API_BASE_URL", "NODE_ENV"]) {
    anterior[k] = process.env[k];
    if (amb[k] === undefined) delete process.env[k];
    else process.env[k] = amb[k];
  }
  try {
    const url = pathToFileURL(MODULO_API).href + `?t=${Math.random()}`;
    const mod = await import(url);
    return mod.API_BASE_URL;
  } finally {
    for (const [k, v] of Object.entries(anterior)) {
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
  }
}

test("o servidor prefere o endereco LOCAL (API_INTERNAL_URL)", async () => {
  const base = await baseCom({
    API_INTERNAL_URL: "http://127.0.0.1:5101",
    NEXT_PUBLIC_API_BASE_URL: "http://dev.portal-noticias.com.br",
  });
  assert.equal(
    base,
    "http://127.0.0.1:5101",
    `o servidor nao usou API_INTERNAL_URL; foi para "${base}". E o hostname publico nao resolve da VPS -- e essa e a razao do bug.`
  );
});

test("sem API_INTERNAL_URL, o servidor ainda cai na origem publica (nao quebra)", async () => {
  const base = await baseCom({
    API_INTERNAL_URL: undefined,
    NEXT_PUBLIC_API_BASE_URL: "http://dev.portal-noticias.com.br",
  });
  assert.equal(base, "http://dev.portal-noticias.com.br");
});

test("sem nenhuma das duas, o fallback de desenvolvimento permanece", async () => {
  const base = await baseCom({
    API_INTERNAL_URL: undefined,
    NEXT_PUBLIC_API_BASE_URL: undefined,
  });
  assert.equal(base, "http://localhost:8000", "o fallback de dev local mudou; `next dev` sem .env pararia de funcionar");
});

test("a variavel do servidor NAO pode ser NEXT_PUBLIC_ (vazaria o bundle do navegador)", async () => {
  // Se algum dia `API_INTERNAL_URL` virar `NEXT_PUBLIC_*`, o valor
  // `http://127.0.0.1:5101` passa a ser embutido no bundle entregue ao
  // navegador — endereço que não existe na máquina de quem lê, mais a porta
  // interna do gunicorn exposta. Este teste trava o sufixo.
  const fs = await import("node:fs");
  const fonte = fs.readFileSync(MODULO_API, "utf8");
  assert.doesNotMatch(
    fonte,
    /NEXT_PUBLIC_API_INTERNAL_URL/,
    "API_INTERNAL_URL virou NEXT_PUBLIC_*: o endereco local do gunicorn passa a ir para o navegador"
  );
  // E o guard de navegador precisa continuarFIando antes de qualquer escolha.
  assert.match(
    fonte,
    /typeof window !== "undefined"[\s\S]{0,120}NODE_ENV === "production"[\s\S]{0,40}\?\s*""/,
    "o ramo de navegador (mesma origem) nao esta mais primeiro; o cliente passaria a usar endereco interno"
  );
});

test("o proxy /api/* e a lib da API leem a MESMA variavel de runtime", async () => {
  // Se os dois lados usarem variaveis diferentes, o navegador funciona e o
  // servidor nao — que e exatamente o bug, em outra forma. Eles tem que
  // concordar no nome.
  const fs = await import("node:fs");
  const proxy = fs.readFileSync(path.join(RAIZ, "app", "api", "[...path]", "route.ts"), "utf8");
  const lib = fs.readFileSync(MODULO_API, "utf8");
  assert.match(proxy, /process\.env\.API_INTERNAL_URL/, "o proxy /api/* parou de usar API_INTERNAL_URL");
  assert.match(lib, /process\.env\.API_INTERNAL_URL/, "lib/api.ts parou de usar API_INTERNAL_URL");
});