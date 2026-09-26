/*
 * Verificação da política de cache do TanStack Query (política conservadora):
 *   - público staleTime 60s; autenticado 15s; telas de decisão 0s;
 *   - sem persistência localStorage/IndexedDB; cache somente em memória;
 *   - chaves sem token/PII (usuario.id apenas); logout limpa cache.
 *
 * Node puro (ESM, sem dependências), lendo os fontes diretamente. Os caminhos
 * são resolvidos relativos a este arquivo (import.meta.url), portanto o script
 * roda de qualquer diretório: node frontend/scripts/verificar-query-client.mjs
 *
 * Saída: uma linha por verificação com [OK]/[VIOLAÇÃO] e detalhes.
 * Exit code: 1 em qualquer violação (ou erro inesperado), 0 se tudo passa.
 */
import { readFile, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const dirScript = path.dirname(fileURLToPath(import.meta.url));
const dirFrontend = path.resolve(dirScript, "..");
const dirApp = path.join(dirFrontend, "app");

const violacoes = [];

function registrar(nome, ok, detalhes) {
  console.log(`[${ok ? "OK" : "VIOLAÇÃO"}] ${nome}${detalhes ? ` — ${detalhes}` : ""}`);
  if (!ok) violacoes.push(nome);
}

function linhaDe(fonte, indice) {
  let linha = 1;
  for (let i = 0; i < indice && i < fonte.length; i += 1) {
    if (fonte[i] === "\n") linha += 1;
  }
  return linha;
}

/**
 * Remove comentários de linha e de bloco preservando strings e a contagem de
 * linhas. Necessário porque o próprio query-client.ts menciona "dehydrate" e
 * "hydrate" dentro de um comentário — os identificadores proibidos só valem
 * em código. Iteração caractere a caractere para não depender de regex frágil
 * com strings contendo "//" (URLs) nem de tipos experimentais do Node.
 */
function removerComentarios(fonte) {
  let saida = "";
  let i = 0;
  // codigo | linha | bloco | aspasSimples | aspasDuplas | template
  let modo = "codigo";
  while (i < fonte.length) {
    const caractere = fonte[i];
    const proximo = fonte[i + 1];
    if (modo === "codigo") {
      if (caractere === "/" && proximo === "/") { modo = "linha"; i += 2; continue; }
      if (caractere === "/" && proximo === "*") { modo = "bloco"; i += 2; continue; }
      if (caractere === "'") { modo = "aspasSimples"; saida += caractere; i += 1; continue; }
      if (caractere === '"') { modo = "aspasDuplas"; saida += caractere; i += 1; continue; }
      if (caractere === "`") { modo = "template"; saida += caractere; i += 1; continue; }
      saida += caractere; i += 1; continue;
    }
    if (modo === "linha") {
      if (caractere === "\n") { modo = "codigo"; saida += "\n"; }
      i += 1; continue;
    }
    if (modo === "bloco") {
      if (caractere === "*" && proximo === "/") { modo = "codigo"; i += 2; continue; }
      if (caractere === "\n") saida += "\n";
      i += 1; continue;
    }
    // Dentro de string: preserva tudo, tratando escapes (\", \`, \\ ...).
    if (caractere === "\\") { saida += caractere + (proximo ?? ""); i += 2; continue; }
    if (
      (modo === "aspasSimples" && caractere === "'") ||
      (modo === "aspasDuplas" && caractere === '"') ||
      (modo === "template" && caractere === "`")
    ) { modo = "codigo"; }
    saida += caractere; i += 1;
  }
  return saida;
}

async function lerFonte(caminho) {
  return removerComentarios(await readFile(caminho, "utf8"));
}

async function arquivosRecursivos(dir) {
  const encontrados = [];
  for (const entrada of await readdir(dir, { withFileTypes: true })) {
    const caminho = path.join(dir, entrada.name);
    if (entrada.isDirectory()) encontrados.push(...await arquivosRecursivos(caminho));
    else if (entrada.isFile()) encontrados.push(caminho);
  }
  return encontrados;
}

async function main() {
  // ---- 1. frontend/lib/query-client.ts ----
  const fonteQueryClient = await lerFonte(path.join(dirFrontend, "lib", "query-client.ts"));

  const temStaleTimePublico =
    /STALE_TIME_PUBLICO_MS\s*=\s*60_?000/.test(fonteQueryClient) &&
    /staleTime:\s*STALE_TIME_PUBLICO_MS/.test(fonteQueryClient);
  registrar(
    "query-client.ts: staleTime público = 60_000 (padrão do client)",
    temStaleTimePublico,
    temStaleTimePublico
      ? "STALE_TIME_PUBLICO_MS = 60_000 usado como staleTime padrão"
      : "esperado `STALE_TIME_PUBLICO_MS = 60_000` e `staleTime: STALE_TIME_PUBLICO_MS`"
  );

  const proibidosClient = /persistQueryClient|createAsyncStoragePersister|dehydrate|hydrate|localStorage|IndexedDB/gi;
  const encontradosClient = [...new Set(fonteQueryClient.match(proibidosClient) ?? [])];
  registrar(
    "query-client.ts: sem persistência (cache somente em memória)",
    encontradosClient.length === 0,
    encontradosClient.length === 0
      ? "persistQueryClient/dehydrate/hydrate/localStorage/IndexedDB ausentes do código (comentários ignorados)"
      : `encontrado(s): ${encontradosClient.join(", ")}`
  );

  // ---- 2. frontend/lib/query-keys.ts ----
  const fonteQueryKeys = await lerFonte(path.join(dirFrontend, "lib", "query-keys.ts"));

  const tokenEmKeys = [...fonteQueryKeys.matchAll(/\btoken\b/gi)];
  registrar(
    "query-keys.ts: nenhuma chave contém token",
    tokenEmKeys.length === 0,
    tokenEmKeys.length === 0
      ? "nenhuma ocorrência de \"token\" no código (elemento de chave, propriedade ou identificador); AMBIENTE_QUERY (NEXT_PUBLIC_API_BASE_URL) é permitido"
      : `ocorrências de \"token\" nas linhas ${[...new Set(tokenEmKeys.map((match) => linhaDe(fonteQueryKeys, match.index)))].join(", ")}`
  );

  // ---- 3. frontend/lib/queries.ts ----
  const fonteQueries = await lerFonte(path.join(dirFrontend, "lib", "queries.ts"));

  const temStaleTimes =
    /STALE_TIME_PUBLICO_MS\s*=\s*60_?000/.test(fonteQueries) &&
    /STALE_TIME_PRIVADO_MS\s*=\s*15_?000/.test(fonteQueries) &&
    /staleTime:\s*STALE_TIME_PUBLICO_MS/.test(fonteQueries) &&
    /staleTime:\s*STALE_TIME_PRIVADO_MS/.test(fonteQueries);
  registrar(
    "queries.ts: staleTimes presentes (público 60_000, privado 15_000)",
    temStaleTimes,
    temStaleTimes
      ? "STALE_TIME_PUBLICO_MS = 60_000 e STALE_TIME_PRIVADO_MS = 15_000 definidos e usados"
      : "esperados `STALE_TIME_PUBLICO_MS = 60_000` e `STALE_TIME_PRIVADO_MS = 15_000` usados em staleTime"
  );

  const blocosUseQuery = [...fonteQueries.matchAll(/useQuery\(\{([\s\S]*?)\}\);/g)];
  const blocosSemQueryKey = blocosUseQuery.filter(
    (bloco) => !/queryKey:\s*queryKeys\./.test(bloco[1])
  );
  registrar(
    "queries.ts: hooks de leitura usam queryKeys.*",
    blocosUseQuery.length > 0 && blocosSemQueryKey.length === 0,
    blocosUseQuery.length === 0
      ? "nenhum useQuery({ ... }) encontrado em queries.ts"
      : blocosSemQueryKey.length === 0
        ? `${blocosUseQuery.length} hook(s) de leitura, todos com queryKey de queryKeys.*`
        : `${blocosSemQueryKey.length} hook(s) sem queryKeys.*: ${blocosSemQueryKey.map((bloco) => linhaDe(fonteQueries, bloco.index)).join(", ")}`
  );

  const chavesComToken = [];
  for (const bloco of blocosUseQuery) {
    for (const linha of bloco[1].split("\n")) {
      const matchChave = linha.match(/^\s*queryKey:\s*(.+?),?\s*$/);
      if (matchChave && /\btoken\b/i.test(matchChave[1])) {
        chavesComToken.push(`${linhaDe(fonteQueries, bloco.index)}: ${matchChave[1].trim()}`);
      }
    }
  }
  const linhasSoltasComToken = fonteQueries
    .split("\n")
    .map((linha, indice) => ({ linha, indice }))
    .filter(({ linha }) => /queryKey/.test(linha) && /\btoken\b/i.test(linha))
    .map(({ linha, indice }) => `${indice + 1}: ${linha.trim()}`);
  registrar(
    "queries.ts: nenhuma queryKey recebe token como argumento",
    chavesComToken.length === 0 && linhasSoltasComToken.length === 0,
    chavesComToken.length === 0 && linhasSoltasComToken.length === 0
      ? "credenciais ficam no closure do queryFn; queryKey usa somente usuarioId/filtros"
      : [...chavesComToken, ...linhasSoltasComToken].join(" | ")
  );

  // ---- 4. Telas de decisão (informativo: ausência não é falha) ----
  const staleTimesZero = [...fonteQueries.matchAll(/staleTime:\s*0\b/g)];
  registrar(
    "telas de decisão: hooks com staleTime 0 são permitidos",
    true,
    staleTimesZero.length > 0
      ? `${staleTimesZero.length} hook(s) com staleTime 0 (linha(s) ${[...new Set(staleTimesZero.map((match) => linhaDe(fonteQueries, match.index)))].join(", ")}) — permitido`
      : "nenhum hook com staleTime 0 no momento (ausência não é falha)"
  );

  // ---- 5. Varredura frontend/app/** ----
  const extensoesFonte = /\.(ts|tsx|js|jsx|mjs|cjs|mts|cts)$/;
  const proibidosApp = /persistQueryClient|createAsyncStoragePersister/;
  const arquivosApp = (await arquivosRecursivos(dirApp)).filter((arquivo) => extensoesFonte.test(arquivo));
  const encontradosApp = [];
  for (const caminho of arquivosApp) {
    let fonte;
    try {
      fonte = removerComentarios(await readFile(caminho, "utf8"));
    } catch (erro) {
      encontradosApp.push(`${path.relative(dirFrontend, caminho)}: falha ao ler (${erro?.message ?? String(erro)})`);
      continue;
    }
    const linhas = fonte.split("\n");
    for (let i = 0; i < linhas.length; i += 1) {
      if (proibidosApp.test(linhas[i])) {
        encontradosApp.push(`${path.relative(dirFrontend, caminho)}:${i + 1}`);
      }
    }
  }
  registrar(
    "frontend/app/**: sem persistQueryClient/createAsyncStoragePersister",
    encontradosApp.length === 0,
    encontradosApp.length === 0
      ? `${arquivosApp.length} arquivo(s) de fonte varridos`
      : `encontrado(s): ${encontradosApp.join(", ")}`
  );

  if (violacoes.length > 0) {
    console.error(`\n${violacoes.length} verificação(ões) em VIOLAÇÃO da política de cache do query client.`);
    process.exit(1);
  }
  console.log("\nPolítica de cache do query client OK.");
}

main().catch((erro) => {
  console.error(`[VIOLAÇÃO] falha inesperada na verificação: ${erro?.message ?? String(erro)}`);
  process.exit(1);
});
