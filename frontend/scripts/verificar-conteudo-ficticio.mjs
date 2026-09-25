/*
 * Guarda de regressão contra conteúdo FICTÍCIO em produção
 * (implementation-contract.md run 20260925-1020-observabilidade,
 * critérios 11 e 12: "não existe fallback fictício silencioso").
 *
 * Node puro (ESM, sem dependências), lendo os fontes diretamente. Os caminhos
 * são resolvidos relativos a este arquivo (import.meta.url), portanto o script
 * roda de qualquer diretório: node frontend/scripts/verificar-conteudo-ficticio.mjs
 *
 * O que é verificado:
 *  1. Nenhum identificador de array/objeto de demonstração nas páginas de
 *     produção (MOCK, MOCK_PUBS, MOCK_T, FONTES_MOCK, mockSerie, ...).
 *  2. Nenhum texto que anuncie conteúdo de exemplo ("Dados de exemplo",
 *     "exibindo dados de exemplo", "API offline — exibindo dados de exemplo",
 *     "manchete demonstrativa", ...).
 *  3. Nenhum e-mail de exemplo de pessoa fictícia (dominio @exemplo.com).
 *  4. Nenhum `Math.random()` em código de página renderizado ao usuário — era
 *     como a série do Radar mudava de valor a cada render.
 *  5. CAUSA RAIZ: `carregarHome` (lib/recomendacao.ts) não pode engolir falha.
 *     Era um `catch { return { secoes: null, feed: [], destaques: [] } }` que
 *     tornava código morto todo o tratamento de erro das páginas consumidoras
 *     — o que, por sua vez, obrigava cada página a inventar um fallback.
 *  6. A Home precisa de tratamento de erro de verdade: nem `MOCK` nem um
 *     `catch` que devolve conteúdo inventado.
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
const dirLib = path.join(dirFrontend, "lib");

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
 * Remove comentários preservando a contagem de linhas. Necesário porque os
 * PRÓPRIOS arquivos descrevem o problema em comentário ("havia um MOCK aqui",
 * "sem MOCK", "exibindo dados de exemplo") — os identificadores proibidos
 * só valem em código executável. Iteração caractere a caractere para não
 * depender de regex frágil com strings contendo "//" (URLs).
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

async function arquivosRecursivos(dir, extensoes) {
  const encontrados = [];
  for (const entrada of await readdir(dir, { withFileTypes: true })) {
    const caminho = path.join(dir, entrada.name);
    // node_modules/.next dentro de app/ não existem, mas pulamos diretórios
    // ocultos e de build por segurança.
    if (entrada.isDirectory()) {
      if (entrada.name.startsWith(".") || entrada.name === "node_modules") continue;
      encontrados.push(...await arquivosRecursivos(caminho, extensoes));
    } else if (entrada.isFile() && extensoes.test(entrada.name)) {
      encontrados.push(caminho);
    }
  }
  return encontrados;
}

/**
 * Padrões proibidos. Cada entrada é [rótulo, RegExp sem `g`] — o `g` é
 * adicionado em tempo de busca para poder iterar com `matchAll`.
 *
 * Os identificadores são anchors de PALAVRA (`\b`): `mock` sozinho aparece em
 * biblioteca legítima e não pode ser proibido; `MOCK`, `MOCK_PUBS` e
 * `mockSerie` são os nomes usados pelas páginas como array de demonstração.
 *
 * `conteúdo de exemplo` tem lookbehind negativo para as frases de política
 * ("não exibimos conteúdo de exemplo"): as telas honestas PRECISAM poder dizer
 * isso — é o comportamento que a política exige, e é a única forma de o
 * usuário saber que não está vendo dado inventado. Um verificador que obriga a
 * apagar a explicação honesta é um verificador que se contorna. O lookbehind do
 * JavaScript aceita comprimento variável, o que permite isentar o verbo
 * ("não exibimos", "não mostramos", ...) sem listar a frase inteira.
 */
const NEGACAO_DE_EXEMPLO =
  "(?<!não (?:exibimos|mostramos|listamos|adicionamos|oferecemos|inserimos|usamos|substituímos|substituimos|publicamos)\\s)";

const PADROES_FICCAO = [
  ["array de demonstração (MOCK*)", /\bMOCK[A-Za-z0-9_]*\b/],
  ["gerador de série fictícia (mock*)", /\bmock[A-Za-z0-9_]*\s*\(/],
  ["texto de 'dados de exemplo'", /dados de exemplo/i],
  ["anúncio de fallback fictício", /exibindo (dados|conteúdo) de exemplo/i],
  ["'API offline' como diagnóstico de tela", /API offline/i],
  [
    "manchete/notícia de demonstração",
    new RegExp(
      `manchete demonstrativa|conteúdo de demonstração|${NEGACAO_DE_EXEMPLO}conteúdo de exemplo`,
      "i"
    ),
  ],
  ["fonte de exemplo", /Fonte Exemplo/],
  ["resumo de fallback fictício", /Resumo de fallback|conteúdo demonstrativo/i],
  ["e-mail de pessoa fictícia", /[\w.+-]+@exemplo\.com\b/],
  ["aleatoriedade em página de produção", /Math\.random\s*\(/],
];

/**
 * `placeholder="voce@exemplo.com"` é dica de preenchimento de campo, não dado
 * fictício: o usuário digita o próprio endereço ali. O que a política proíbe é o
 * endereço aparecer como DADO de uma pessoa que não existe (uma lista de
 * usuários, um log de atividade). Logo, a linha inteira é isenta quando o
 * e-mail só aparece dentro de um `placeholder`.
 */
const SO_PLACEHOLDER_DE_EMAIL = /placeholder\s*=\s*["'][^"']*@exemplo\.com/;

/** Arquivos que NÃO podem conter nenhum dos padrões acima. */
const ARQUIVOS_VIGIADOS = [
  "app/page.tsx",
  "app/ao-vivo/page.tsx",
  "app/arquivo/page.tsx",
  "app/buscar/page.tsx",
  "app/categoria/[slug]/page.tsx",
  "app/noticia/[id]/page.tsx",
  "app/comunidade/page.tsx",
  "app/radar/RadarClient.tsx",
  "app/noticia/cluster/[id]/page.tsx",
  "app/noticia/item/[id]/page.tsx",
  "app/admin/page.tsx",
  "app/admin/usuarios/page.tsx",
  "app/admin/moderacao/page.tsx",
  "app/admin/fila/page.tsx",
  "app/admin/planos/page.tsx",
  "app/admin/limites/page.tsx",
  "app/admin/assinaturas/page.tsx",
  "app/admin/robos/page.tsx",
];

/** `lib/` inteiro é varrido: um fallback pode nascer fora de `app/`. */
async function varrerApp() {
  const arquivos = await arquivosRecursivos(dirApp, /\.(ts|tsx|js|jsx|mjs|cjs|mts|cts)$/);
  const achados = [];
  for (const caminho of arquivos) {
    let fonte;
    try {
      fonte = await lerFonte(caminho);
    } catch (erro) {
      achados.push(`${path.relative(dirFrontend, caminho)}: falha ao ler (${erro?.message ?? String(erro)})`);
      continue;
    }
    const linhas = fonte.split("\n");
    for (const [rotulo, padrao] of PADROES_FICCAO) {
      const re = new RegExp(padrao.source, padrao.flags.includes("g") ? padrao.flags : `${padrao.flags}g`);
      for (const achado of fonte.matchAll(re)) {
        const linha = linhaDe(fonte, achado.index);
        if (rotulo.startsWith("e-mail") && SO_PLACEHOLDER_DE_EMAIL.test(linhas[linha - 1] ?? "")) continue;
        achados.push(
          `${path.relative(dirFrontend, caminho)}:${linha} — ${rotulo} ("${achado[0].slice(0, 60)}")`
        );
      }
    }
  }
  return { arquivos, achados };
}

async function varrerLib() {
  const arquivos = await arquivosRecursivos(dirLib, /\.(ts|tsx)$/);
  const achados = [];
  for (const caminho of arquivos) {
    let fonte;
    try {
      fonte = await lerFonte(caminho);
    } catch (erro) {
      achados.push(`${path.relative(dirFrontend, caminho)}: falha ao ler (${erro?.message ?? String(erro)})`);
      continue;
    }
    // Em `lib/` o que vale proibir é o array/gerador de demonstração. Texto de
    // "dados de exemplo" e `Math.random()` são legítimos em utilitários
    // (ex.: `ImagemNoticia` deriva gradiente do slug com hash determinístico;
    // `analytics.ts` usa Math.random só para um id de sessão local, que nunca
    // sai do navegador).
    for (const [rotulo, padrao] of [
      ["array de demonstração (MOCK*)", /\bMOCK[A-Za-z0-9_]*\b/],
      ["gerador de série fictícia (mock*)", /\bmock[A-Za-z0-9_]*\s*\(/],
      ["e-mail de pessoa fictícia", /[\w.+-]+@exemplo\.com\b/],
    ]) {
      const re = new RegExp(padrao.source, `${padrao.flags}g`);
      for (const achado of fonte.matchAll(re)) {
        achados.push(
          `${path.relative(dirFrontend, caminho)}:${linhaDe(fonte, achado.index)} — ${rotulo} ("${achado[0].slice(0, 60)}")`
        );
      }
    }
  }
  return { arquivos, achados };
}

/** `catch` que engole erro devolvendo lista/seções vazias é a raiz do problema. */
const ENGOLIR_FALHA = /catch\s*(?:\([^)]*\))?\s*\{[^}]*return\s*\{[^}]*\b(secoes|feed|itens|resultados|destaques)\s*:\s*(null|\[\])/;

async function main() {
  console.log(`Vigiliando ${ARQUIVOS_VIGIADOS.length} páginas conhecidas + toda a árvore app/ e lib/.\n`);

  // ---- 0. Arquivos de página que o contrato nomeia: todos precisam existir --
  const faltando = [];
  for (const relativo of ARQUIVOS_VIGIADOS) {
    try {
      await readFile(path.join(dirFrontend, relativo), "utf8");
    } catch {
      faltando.push(relativo);
    }
  }
  registrar(
    "páginas vigiadas existem",
    faltando.length === 0,
    faltando.length === 0
      ? `${ARQUIVOS_VIGIADOS.length} arquivo(s) encontrado(s)`
      : `não encontrado(s): ${faltando.join(", ")}`
  );

  // ---- 1. app/** sem padrão de conteúdo fictício ---------------------------
  const app = await varrerApp();
  registrar(
    "frontend/app/**: sem array/objeto/texto de demonstração",
    app.achados.length === 0,
    app.achados.length === 0
      ? `${app.arquivos.length} arquivo(s) de fonte varridos (comentários ignorados)`
      : `${app.achados.length} achado(s):\n      - ${app.achados.join("\n      - ")}`
  );

  // ---- 2. lib/** sem array/gerador de demonstração -------------------------
  const lib = await varrerLib();
  registrar(
    "frontend/lib/**: sem array/objeto de demonstração",
    lib.achados.length === 0,
    lib.achados.length === 0
      ? `${lib.arquivos.length} arquivo(s) de fonte varridos (comentários ignorados)`
      : `${lib.achados.length} achado(s):\n      - ${lib.achados.join("\n      - ")}`
  );

  // ---- 3. Causa raiz: carregarHome não pode engolir falha ------------------
  const fonteRecomendacao = await lerFonte(path.join(dirLib, "recomendacao.ts"));
  const inicio = fonteRecomendacao.search(/export\s+async\s+function\s+carregarHome\b/);
  let corpoCarregarHome = "";
  if (inicio >= 0) {
    const fim = fonteRecomendacao.indexOf("\nexport ", inicio + 1);
    corpoCarregarHome = fonteRecomendacao.slice(inicio, fim > 0 ? fim : undefined);
  }
  registrar(
    "lib/recomendacao.ts: carregarHome existe e propaga falha",
    inicio >= 0 && !ENGOLIR_FALHA.test(corpoCarregarHome),
    inicio < 0
      ? "carregarHome não encontrado em lib/recomendacao.ts"
      : ENGOLIR_FALHA.test(corpoCarregarHome)
        ? "carregarHome tem `catch` devolvendo seção/lista vazia — todo tratamento de erro das páginas que a consomem vira código morto e o fallback fictício volta"
        : "sem `catch` que converta falha em lista/seção vazia"
  );

  // ---- 4. Home tem tratamento de erro de verdade ---------------------------
  const fonteHome = await lerFonte(path.join(dirApp, "page.tsx"));
  const temCatch = /\bcatch\b/.test(fonteHome);
  const usaUltimoReal = /ultimo-conteudo-real/.test(fonteHome);
  registrar(
    "app/page.tsx: falha real é tratada (janela de stale + honestidade)",
    temCatch && usaUltimoReal,
    !temCatch
      ? "sem `catch`: a Home não distingue falha de base vazia"
      : !usaUltimoReal
        ? "sem janela de último conteúdo real (`ultimo-conteudo-real`): na falha a Home não tem o que servir honestamente"
        : "`catch` presente com janela de último conteúdo real de 5 min"
  );

  // ---- 5. 503 no feed: a rota de proxy precisa distinguir e reportar -------
  const fonteProxy = await lerFonte(path.join(dirApp, "api", "[...path]", "route.ts"));
  const temTetoBody = /MAX_BODY_BYTES/.test(fonteProxy);
  const temTimeout = /AbortController/.test(fonteProxy) && /TIMEOUT/.test(fonteProxy);
  const temRequestId = /X-Request-ID/.test(fonteProxy);
  registrar(
    "app/api/[...path]/route.ts: timeout, teto de body e correlação",
    temTetoBody && temTimeout && temRequestId,
    !temRequestId
      ? "sem propagação de X-Request-ID"
      : !temTimeout
        ? "sem timeout via AbortController"
        : !temTetoBody
          ? "sem teto de tamanho de body (upload de credenciamento carrega foto+PDF inteiros na memória)"
          : "timeout, teto de body e X-Request-ID presentes"
  );

  if (violacoes.length > 0) {
    console.error(`\n${violacoes.length} verificação(ões) em VIOLAÇÃO da política de conteúdo real.`);
    process.exit(1);
  }
  console.log("\nNenhum fallback fictício encontrado nas páginas de produção.");
}

main().catch((erro) => {
  console.error(`[VIOLAÇÃO] falha inesperada na verificação: ${erro?.message ?? String(erro)}`);
  process.exit(1);
});
