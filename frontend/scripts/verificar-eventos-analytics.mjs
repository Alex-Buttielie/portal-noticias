#!/usr/bin/env node
/**
 * Guarda de regressão P1-10 — "Eventos externos só após consentimento; sem
 * token/query string".
 *
 * Mesmo desenho da guarda de P1-09 (o projeto não tem runner de teste de
 * componente e dependência está fora do escopo):
 *
 *  A) COMPORTAMENTAL, sobre `lib/analytics.ts` REAL: importa o módulo (Node 24
 *     remove os tipos; o resolver local resolve import sem extensão) e
 *     exercita `caminhoSeguro`, `redigirTexto`, `redigirObjeto`,
 *     `montarCorpoEvento` e `enviarEvento` com `navigator`/`fetch` dublês.
 *     `enviarEvento` é chamada de verdade, então a forma da requisição
 *     (URL, cabeçalhos, corpo) é observada, não suposta.
 *
 *  B) ESTÁTICA, sobre os fontes: o que a prova comportamental não alcança —
 *     que a checagem de consentimento vem ANTES do envio, que ninguém
 *     reintroduziu `location.search` no `path`, e que não existe ID de
 *     medição (GA4) escrito à mão.
 *
 * Cada regra estática é função pura e tem autoteste com caso NEGATIVO (a
 * regra precisa reprovar) e caso de FALSO POSITIVO (a regra precisa aceitar
 * código inocente que só parece suspeito).
 *
 * Uso:  node scripts/verificar-eventos-analytics.mjs
 * Sai com 0 se tudo passa; 1 com a lista de violações.
 */
import { readdir, readFile } from "node:fs/promises";
import { registerHooks } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import fs from "node:fs";
import path from "node:path";

const dirScript = path.dirname(fileURLToPath(import.meta.url));
const dirFrontend = path.resolve(dirScript, "..");

// --- resolver local (o Next resolve `@/` e import sem extensão; o Node, não) --
const EXTENSOES = ["", ".ts", ".tsx", ".mts", ".js", ".mjs", "/index.ts", "/index.tsx"];
function existeArquivo(base) {
  for (const extensao of EXTENSOES) {
    const candidato = String(base + extensao);
    if (fs.existsSync(candidato) && fs.statSync(candidato).isFile()) {
      return pathToFileURL(candidato).href;
    }
  }
  return null;
}
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith("@/")) {
      const url = existeArquivo(path.join(dirFrontend, specifier.slice(2)));
      if (url) return { url, shortCircuit: true };
    }
    if (specifier.startsWith("./") || specifier.startsWith("../")) {
      const pai = context.parentURL ? path.dirname(fileURLToPath(context.parentURL)) : dirFrontend;
      const url = existeArquivo(path.resolve(pai, specifier));
      if (url) return { url, shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
});

const AVISO_REPARSE = "Module type of ";
process.removeAllListeners("warning");
process.on("warning", (aviso) => {
  if (typeof aviso?.message === "string" && aviso.message.startsWith(AVISO_REPARSE)) return;
  console.warn(`[aviso] ${aviso?.name ?? "Warning"}: ${aviso?.message ?? String(aviso)}`);
});

const violacoes = [];
const autotestes = [];

function registrar(nome, ok, detalhes) {
  console.log(`[${ok ? "OK" : "VIOLAÇÃO"}] ${nome}${detalhes ? ` — ${detalhes}` : ""}`);
  if (!ok) violacoes.push(nome);
}

function registrarAutoteste(nome, ok, detalhes) {
  autotestes.push({ nome, ok });
  console.log(`  ${ok ? "·" : "FALHOU"} autoteste: ${nome}${detalhes ? ` — ${detalhes}` : ""}`);
  if (!ok) violacoes.push(`autoteste: ${nome}`);
}

function linhaDe(fonte, indice) {
  let linha = 1;
  for (let i = 0; i < indice && i < fonte.length; i += 1) {
    if (fonte[i] === "\n") linha += 1;
  }
  return linha;
}

/** Remove comentários preservando strings e a contagem de linhas. */
function removerComentarios(fonte) {
  let saida = "";
  let i = 0;
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

async function arquivosRecursivos(dir) {
  const encontrados = [];
  let entradas;
  try {
    entradas = await readdir(dir, { withFileTypes: true });
  } catch {
    return encontrados;
  }
  for (const entrada of entradas) {
    if (entrada.name === "node_modules" || entrada.name === ".next") continue;
    const caminho = path.join(dir, entrada.name);
    if (entrada.isDirectory()) encontrados.push(...(await arquivosRecursivos(caminho)));
    else if (entrada.isFile()) encontrados.push(caminho);
  }
  return encontrados;
}

const EXTENSOES_FONTE = /\.(ts|tsx|js|jsx|mjs|cjs|mts|cts)$/;
const DIRETORIOS_VARRIDOS = ["app", "components", "lib"];

/**
 * Isola o corpo de uma função exportada por nome. Usado para que uma regra
 * examine SÓ o código que executa no caminho do evento — senão a palavra
 * "Authorization" dentro da lista de redação, ou o `location.search` que a
 * `detectarOrigem` usa para classificar UTM, acusariam a si mesmos.
 */
function corpoDaFuncao(fonte, nome) {
  const inicio = fonte.search(new RegExp(`(?:export\\s+)?function\\s+${nome}\\s*\\(`));
  if (inicio < 0) return null;
  const abre = fonte.indexOf("{", inicio);
  if (abre < 0) return null;
  let profundidade = 0;
  for (let i = abre; i < fonte.length; i += 1) {
    if (fonte[i] === "{") profundidade += 1;
    else if (fonte[i] === "}") {
      profundidade -= 1;
      if (profundidade === 0) return { texto: fonte.slice(abre, i + 1), inicio: abre };
    }
  }
  return { texto: fonte.slice(abre), inicio: abre };
}

// ---------------------------------------------------------------------------
// Regras estáticas (funções puras — autotestáveis)
// ---------------------------------------------------------------------------

/**
 * R1: `track()` tem de recusar ANTES de montar/enviar. A ordem é a barreira:
 * se `consentido()` for checado depois de `enviarEvento`, um erro em
 * `detectarDispositivo` já teria disparado o pedido sem consentimento.
 */
function regraConsentimentoAntesDoEnvio(caminho, fonte) {
  if (path.basename(caminho) !== "analytics.ts") return { ok: true, detalhes: "não é analytics.ts" };
  const corpo = corpoDaFuncao(fonte, "track");
  if (!corpo) return { ok: true, detalhes: "sem `export function track` neste arquivo (nada a ordenar)" };
  const posConsent = corpo.texto.search(/if\s*\(\s*!\s*consentido\s*\(\s*\)\s*\)\s*return false\s*;?/);
  const posEnvio = corpo.texto.search(/enviarEvento\s*\(|navigator\.sendBeacon|fetch\s*\(/);
  if (posConsent < 0) {
    return { ok: false, detalhes: "`track` não tem `if (!consentido()) return false;`" };
  }
  if (posEnvio < 0) {
    return { ok: true, detalhes: "`track` não envia nada por conta própria" };
  }
  return {
    ok: posConsent < posEnvio,
    detalhes:
      posConsent < posEnvio
        ? `consentimento checado na linha ${linhaDe(fonte, corpo.inicio + posConsent)}, envio na linha ${linhaDe(fonte, corpo.inicio + posEnvio)}`
        : `ENVIO na linha ${linhaDe(fonte, corpo.inicio + posEnvio)} vem ANTES do consentimento na linha ${linhaDe(fonte, corpo.inicio + posConsent)}`,
  };
}

/**
 * R2: `path` de evento nunca é montado a partir de `location.search`,
 * `location.href` ou de `searchParams.toString()`.
 *
 * Escopo: só os dois arquivos que de fato constroem o `path` do evento
 * (`lib/analytics.ts` e `components/AnalyticsTracker.tsx`). `location.href`
 * numa navegação (`window.location.href = "/login"`) não tem nada a ver com
 * analytics, e `detectarOrigem` LER `location.search` para reduzir utm_source a
 * uma CATEGORIA ("campanha") é legítimo — o que não pode é o VALOR entrar no
 * evento. Por isso a regra admite `location.search` dentro de `detectarOrigem`
 * e em nenhum outro lugar.
 */
const USO_LEGITIMO_DE_QUERY = { "lib/analytics.ts": ["detectarOrigem"] };

function regraPathSemQueryString(caminho, fonte) {
  const rel = caminho.split(path.sep).join("/");
  const noEscopo = rel === "lib/analytics.ts" || rel === "components/AnalyticsTracker.tsx";
  if (!noEscopo) return { ok: true, detalhes: "fora do escopo (não monta `path` de evento)" };
  const permitidos = USO_LEGITIMO_DE_QUERY[rel] ?? [];
  const proibidos = [
    [/location\.search/g, "location.search"],
    [/location\.href/g, "location.href"],
    [/searchParams\s*\??\.\s*toString\s*\(/g, "searchParams.toString()"],
  ];
  const achados = [];
  for (const [re, rotulo] of proibidos) {
    for (const m of fonte.matchAll(re)) {
      const dentroDePermitida = permitidos.some((nome) => {
        const corpo = corpoDaFuncao(fonte, nome);
        return corpo && m.index >= corpo.inicio && m.index < corpo.inicio + corpo.texto.length;
      });
      if (!dentroDePermitida) achados.push(`${rotulo} na linha ${linhaDe(fonte, m.index)}`);
    }
  }
  return {
    ok: achados.length === 0,
    detalhes:
      achados.length === 0
        ? permitidos.length > 0
          ? `path só do pathname (leitura de utm em ${permitidos.join(", ")} devolve categoria, não valor)`
          : "path montado só a partir do pathname"
        : achados.join(" | "),
  };
}

/**
 * R3: o CORPO do envio do evento não leva cabeçalho de credencial.
 * `EventoSite` não tem coluna de usuário; um `Authorization` aqui transformaria
 * analytics num canal de identificação do visitante. Escopo: o corpo de
 * `enviarEvento` (e o de `track`), para a lista de palavras reservadas da
 * redação — que é justamente onde "authorization" aparece — não ser réu de si.
 */
function regraSemCabecalhoDeCredencial(caminho, fonte) {
  if (path.basename(caminho) !== "analytics.ts") return { ok: true, detalhes: "não é analytics.ts" };
  const corpo = corpoDaFuncao(fonte, "enviarEvento");
  if (!corpo) return { ok: true, detalhes: "sem `enviarEvento` neste arquivo" };
  const achados = [];
  for (const [re, rotulo] of [
    [/Authorization/i, "Authorization"],
    [/X-Auth/i, "X-Auth*"],
    [/X-Consent-Token/i, "X-Consent-Token"],
    [/credentials\s*:\s*["']include["']/, "credentials: include"],
    [/\btoken\b/i, "token"],
  ]) {
    const m = corpo.texto.match(re);
    if (m) achados.push(`${rotulo} na linha ${linhaDe(fonte, corpo.inicio + m.index)}`);
  }
  return {
    ok: achados.length === 0,
    detalhes:
      achados.length === 0
        ? "enviarEvento manda só Content-Type; sem token, sem Authorization, sem credentials"
        : achados.join(" | "),
  };
}

/**
 * R4: nenhum terceiro de MEDIÇÃO (GA4/GTM) e nenhum ID `G-…` no frontend.
 *
 * Isto não é "GA4 está pronto": é o contrário. O `develop` não tem GA4, e esta
 * guarda é o que impede que alguém introduza uma tag do Google com um ID
 * inventado e sem portão de consentimento. Quando a conta chegar, a
 * implementação tem de entrar por aqui: com `NEXT_PUBLIC_GA4_ID` do ambiente
 * e com o portão de consentimento no mesmo arquivo. A validação real (evento
 * recebido no GA4, Consent Mode refletindo o estado real) fica PENDENTE de
 * conta e não é marcada como verde por este script.
 *
 * Isenção: `lib/anuncios.ts` DECLARA a lista de hosts de medição que NÃO são
 * usados. Quem exige que essa declaração tenha portão de consentimento é a
 * guarda de P1-09 (R1), que varre o mesmo arquivo.
 */
function regraSemTagDeMedicao(caminho, fonte) {
  if (path.basename(caminho) === "anuncios.ts") {
    return { ok: true, detalhes: "declaração de hosts não usados (guarda P1-09 exige portão aqui)" };
  }
  const achados = [];
  const medicao = /googletagmanager\.com|google-analytics\.com|gtag\s*\(|\bdataLayer\b/.exec(fonte);
  if (medicao) achados.push(`tag de medição na linha ${linhaDe(fonte, medicao.index)}`);
  const idMedicao = /["'`]G-[A-Z0-9]{6,}["'`]/.exec(fonte);
  if (idMedicao) achados.push(`ID GA4 literal na linha ${linhaDe(fonte, idMedicao.index)}`);
  return {
    ok: achados.length === 0,
    detalhes:
      achados.length === 0
        ? "sem tag/SDK de medição e sem ID GA4 literal (GA4 = pendente de conta, ver lib/anuncios.ts::GA4_NAO_IMPLEMENTADO)"
        : achados.join(" | "),
  };
}

/**
 * R5: a allowlist de campos do evento existe e é aplicada em `track()`.
 * Sem ela, um chamador novo com `extra: { email }` vazaria em silêncio — o
 * backend do `develop` não tem allowlist própria.
 */
function regraAllowlistDeCampos(caminho, fonte) {
  if (path.basename(caminho) !== "analytics.ts") return { ok: true, detalhes: "não é analytics.ts" };
  const temLista = /export const CAMPOS_EVENTO\s*:\s*readonly string\[\]/.test(fonte);
  const temFiltro = /CAMPOS_EVENTO/.test(fonte) && /montarCorpoEvento/.test(fonte);
  const trackUsa = /montarCorpoEvento\s*\(/.test(fonte);
  return {
    ok: temLista && temFiltro && trackUsa,
    detalhes:
      temLista && temFiltro && trackUsa
        ? "CAMPOS_EVENTO declarado e aplicado por montarCorpoEvento, chamado por track()"
        : `temLista=${temLista} temFiltro=${temFiltro} trackUsa=${trackUsa}`,
  };
}

const REGRAS_ESTATICAS = [
  ["R1", "track() recusa sem consentimento ANTES de enviar", regraConsentimentoAntesDoEnvio],
  ["R2", "path de evento nunca usa query string/URL completa", regraPathSemQueryString],
  ["R3", "nenhum cabeçalho de credencial no evento", regraSemCabecalhoDeCredencial],
  ["R4", "nenhuma tag de medição (GA4/GTM) nem ID literal", regraSemTagDeMedicao],
  ["R5", "allowlist de campos aplicada em track()", regraAllowlistDeCampos],
];

// ---------------------------------------------------------------------------
// Autotestes das regras estáticas
// ---------------------------------------------------------------------------

function rodarAutotestes() {
  console.log("\nAutotestes das regras (negativo = precisa reprovar; falso positivo = precisa aceitar):");

  // R1
  const trackBase = (corpo) => `export function track(payload: PayloadEvento): boolean {\n  if (typeof window === "undefined") return false;\n${corpo}\n}\nexport function trackPageView(){return track({});}\n`;
  registrarAutoteste(
    "R1 negativo: envia antes de checar consentimento (o baseline do develop)",
    regraConsentimentoAntesDoEnvio("lib/analytics.ts", trackBase("  enviarEvento(corpo);\n  if (!consentido()) return false;")).ok === false,
    "reprovado como deve"
  );
  registrarAutoteste(
    "R1 negativo: track sem nenhuma checagem de consentimento",
    regraConsentimentoAntesDoEnvio("lib/analytics.ts", trackBase("  return enviarEvento(corpo);")).ok === false
  );
  registrarAutoteste(
    "R1 falso positivo: consentimento checado antes do envio",
    regraConsentimentoAntesDoEnvio("lib/analytics.ts", trackBase("  if (!consentido()) return false;\n  return enviarEvento(corpo);")).ok === true
  );
  registrarAutoteste(
    "R1 não acusa quem só declara o helper",
    regraConsentimentoAntesDoEnvio("lib/analytics.ts", "export function consentido(){return true;}").ok === true
  );

  // R2
  registrarAutoteste(
    "R2 negativo: path com location.search (o furo do token)",
    regraPathSemQueryString("lib/analytics.ts", "export function montar(){ const path = window.location.pathname + window.location.search; }").ok === false,
    "reprovado como deve"
  );
  registrarAutoteste(
    "R2 negativo: searchParams.toString() no tracker",
    regraPathSemQueryString("components/AnalyticsTracker.tsx", "const path = `${pathname}?${searchParams?.toString()}`;").ok === false
  );
  registrarAutoteste(
    "R2 negativo: location.search dentro de função que NÃO é detectarOrigem",
    regraPathSemQueryString(
      "lib/analytics.ts",
      'export function detectarOrigem(){ const u = new URLSearchParams(window.location.search).get("utm_source"); return u ? "campanha" : "direto"; }\nexport function montar(){ const p = window.location.search; }'
    ).ok === false
  );
  registrarAutoteste(
    "R2 falso positivo: detectarOrigem lendo utm (só a categoria sai)",
    regraPathSemQueryString(
      "lib/analytics.ts",
      'export function detectarOrigem(){ const u = new URLSearchParams(window.location.search).get("utm_source"); return u ? "campanha" : "direto"; }\nexport function track(){ const p = window.location.pathname; }'
    ).ok === true
  );
  registrarAutoteste(
    "R2 falso positivo: só pathname",
    regraPathSemQueryString("lib/analytics.ts", "export function track(){ const p = window.location.pathname; }").ok === true
  );
  registrarAutoteste(
    "R2 não acusa menção em comentário",
    regraPathSemQueryString(
      "lib/analytics.ts",
      removerComentarios("// nunca usar window.location.search no path\nexport function track(){ const p = window.location.pathname; }")
    ).ok === true
  );
  registrarAutoteste(
    "R2 não acusa `location.href` de navegação fora do escopo",
    regraPathSemQueryString("app/comunidade/page.tsx", 'onClick={() => { window.location.href = "/login"; }}').ok === true,
    "navegar para /login não monta `path` de evento"
  );

  // R3
  const enviarBase = (corpo) => `export function enviarEvento(c: unknown): boolean {\n${corpo}\n}\nexport function trackPageView(){ return true; }\n`;
  registrarAutoteste(
    "R3 negativo: Authorization no envio",
    regraSemCabecalhoDeCredencial("lib/analytics.ts", enviarBase('fetch(u, { headers: { "Content-Type": "application/json", Authorization: "Bearer x" } });')).ok === false
  );
  registrarAutoteste(
    "R3 negativo: X-Consent-Token no envio",
    regraSemCabecalhoDeCredencial("lib/analytics.ts", enviarBase('fetch(u, { headers: { "X-Consent-Token": t } });')).ok === false
  );
  registrarAutoteste(
    "R3 negativo: credentials: include no envio",
    regraSemCabecalhoDeCredencial("lib/analytics.ts", enviarBase('fetch(u, { credentials: "include" });')).ok === false
  );
  registrarAutoteste(
    "R3 falso positivo: só Content-Type",
    regraSemCabecalhoDeCredencial("lib/analytics.ts", enviarBase('fetch(u, { headers: { "Content-Type": "application/json" } });')).ok === true
  );
  registrarAutoteste(
    "R3 não acusa a lista de palavras reservadas da redação",
    regraSemCabecalhoDeCredencial(
      "lib/analytics.ts",
      'const CHAVE_SENSIVEL = /authorization|token|email/;\nexport function enviarEvento(c: unknown){ return navigator.sendBeacon(u, c); }'
    ).ok === true,
    "a palavra reservada vive na redação, não no envio"
  );
  registrarAutoteste(
    "R3 não acusa token de sessão na camada autenticada",
    regraSemCabecalhoDeCredencial("lib/api.ts", "export function get(){ headers.Authorization = `Bearer ${token}`; }").ok === true,
    "regra só vale para analytics.ts (api.ts é a camada autenticada, por design)"
  );

  // R4
  registrarAutoteste(
    "R4 negativo: ID GA4 literal",
    regraSemTagDeMedicao("lib/ga4.ts", 'const ID = "G-ABC123XYZ";').ok === false
  );
  registrarAutoteste(
    "R4 negativo: gtag() sem consentimento",
    regraSemTagDeMedicao("components/Ga4.tsx", "window.gtag('config', 'x');").ok === false
  );
  registrarAutoteste("R4 falso positivo: frontend sem GA4", regraSemTagDeMedicao("components/AdsSlot.tsx", "export function AdsSlot(){return null;}").ok === true);
  registrarAutoteste(
    "R4 não acusa a DECLARAÇÃO de hosts não usados",
    regraSemTagDeMedicao("lib/anuncios.ts", 'export const HOSTS_MEDICAO = ["www.google-analytics.com"];').ok === true,
    "a guarda de P1-09 é que exige portão nesses arquivos"
  );

  // R5
  registrarAutoteste(
    "R5 negativo: sem allowlist",
    regraAllowlistDeCampos("lib/analytics.ts", "export function track(){ const c = {...payload}; return enviarEvento(c); }").ok === false
  );
  registrarAutoteste(
    "R5 negativo: allowlist declarada mas não aplicada",
    regraAllowlistDeCampos("lib/analytics.ts", "export const CAMPOS_EVENTO: readonly string[] = [];\nexport function track(){ return enviarEvento(payload); }").ok === false
  );
  registrarAutoteste(
    "R5 falso positivo: allowlist aplicada",
    regraAllowlistDeCampos(
      "lib/analytics.ts",
      "export const CAMPOS_EVENTO: readonly string[] = [\"tipo\"];\nexport function montarCorpoEvento(p){return {...p};}\nexport function track(){ return enviarEvento(montarCorpoEvento(payload, s, p)); }"
    ).ok === true
  );

  // Sanidade: se um autoteste "falso positivo" reprova, ele não é falso
  // positivo — é uma regra barulhenta. Falha alto e cedo.
  const falsosPositivosQueReprovaram = autotestes.filter((a) => a.nome.includes("falso positivo") && !a.ok);
  if (falsosPositivosQueReprovaram.length > 0) {
    console.error(
      `\nAs regras estão acusando código inocente: ${falsosPositivosQueReprovaram.map((a) => a.nome).join(", ")}`
    );
  }
}

// ---------------------------------------------------------------------------

async function main() {
  console.log('P1-10 — Eventos externos só após consentimento; sem token/query string\n');
  console.log("A) Comportamental, sobre lib/analytics.ts real:\n");

  const analytics = await import(path.join(dirFrontend, "lib", "analytics.ts"));

  // ---- B1: caminhoSeguro — o portão anti-token/query string ---------------
  const casosCaminho = [
    ["/verificar-email?token=abc123def", "/verificar-email", "token de verificação de e-mail"],
    ["/newsletter?token=descadastro-9f8", "/newsletter", "token de descadastro de newsletter"],
    ["/buscar?q=segredo+do+buscador", "/buscar", "termo de busca"],
    ["/arquivo?page=7", "/arquivo", "paginação"],
    ["/noticia/12#comentarios", "/noticia/12", "fragmento"],
    ["https://user:senha@exemplo.test/x?a=1#f", "https://exemplo.test/x", "userinfo é credencial"],
    ["/noticia/12", "/noticia/12", "já limpo, não mexe"],
    ["/", "/", "raiz"],
  ];
  for (const [entrada, esperado, porque] of casosCaminho) {
    const obtido = analytics.caminhoSeguro(entrada);
    registrar(`B1 caminhoSeguro("${entrada}")`, obtido === esperado, `${porque} => ${JSON.stringify(obtido)}`);
  }
  const longo = analytics.caminhoSeguro(`/${"a".repeat(900)}`);
  registrar(
    "B1 caminhoSeguro respeita o teto de tamanho",
    longo.length <= 500 && longo.endsWith("…"),
    `${longo.length} caracteres (teto 500), termina em "…"`
  );

  // ---- B2: o corpo do evento nunca leva query string nem campo fora da lista
  const corpo1 = analytics.montarCorpoEvento(
    { tipo: "page_view", path: "/verificar-email?token=SEGRETO123" },
    "s1-abcd",
    "/outra?token=OUTRO"
  );
  registrar(
    "B2 path do evento sai sem query string (do chamador E do navegador)",
    corpo1.path === "/verificar-email",
    `montarCorpoEvento -> path=${JSON.stringify(corpo1.path)}`
  );
  const corpo2 = analytics.montarCorpoEvento(
    { tipo: "page_view", email: "pessoa@exemplo.test", user_id: 42, token: "abc", path: "/x" },
    "s1-abcd",
    "/y"
  );
  registrar(
    "B2 campo fora da allowlist é descartado (email/user_id/token)",
    !("email" in corpo2) && !("user_id" in corpo2) && !("token" in corpo2),
    `chaves do corpo: ${Object.keys(corpo2).join(", ")}`
  );
  const corpo3 = analytics.montarCorpoEvento(
    { tipo: "news_view", extra: { leitura: true, email: "pessoa@exemplo.test", token_sessao: "x", origem: "leitor" } },
    "s1-abcd",
    "/noticia/12"
  );
  registrar(
    "B2 extra: chave sensível vira marcador, campo inocente sobrevive",
    corpo3.extra.leitura === true &&
      corpo3.extra.email === "[redigido]" &&
      corpo3.extra.token_sessao === "[redigido]" &&
      corpo3.extra.origem === "leitor",
    `extra = ${JSON.stringify(corpo3.extra)}`
  );
  const corpo4 = analytics.montarCorpoEvento(
    { tipo: "community_interaction", extra: { contato: "fale comigo em pessoa@exemplo.test" } },
    "s1-abcd",
    "/comunidade"
  );
  registrar(
    "B2 extra: e-mail no VALOR é redigido mesmo com chave inocente",
    corpo4.extra.contato === "fale comigo em [redigido]",
    `extra.contato = ${JSON.stringify(corpo4.extra.contato)}`
  );
  const corpo5 = analytics.montarCorpoEvento({ tipo: "search", termo: "IPTal", filtros: { origem: "pagina_buscar" } }, "s1-abcd", "/buscar");
  registrar(
    "B2 não super-redige: termo e filtro legítimos passam intactos",
    corpo5.termo === "IPTal" && corpo5.filtros.origem === "pagina_buscar",
    `termo=${JSON.stringify(corpo5.termo)} filtros=${JSON.stringify(corpo5.filtros)}`
  );
  registrar(
    "B2 sessao é sempre a da sessão do navegador",
    corpo5.sessao === "s1-abcd",
    `sessao=${JSON.stringify(corpo5.sessao)}`
  );

  // ---- B3: a requisição observada, não suposta ---------------------------
  // `globalThis.navigator` é getter-only no Node 24: redefinir por
  // `defineProperty` (e não por atribuição) para poder observar o beacon.
  const definirNavigator = (valor) =>
    Object.defineProperty(globalThis, "navigator", { value: valor, configurable: true, writable: true });

  const chamadas = [];
  definirNavigator({
    sendBeacon: (...args) => {
      chamadas.push({ url: args[0], blob: args[1], quantidade: args.length });
      return true;
    },
  });
  const enviouBeacon = analytics.enviarEvento({ tipo: "page_view", path: "/noticia/12", sessao: "s1-abcd" });
  const beacon = chamadas[0];
  // O corpo é um `Blob` de verdade; `String(blob)` seria "[object Blob]" e a
  // checagem passaria vazia. Então ele é lido de fato.
  const corpoBeacon = beacon.blob instanceof Blob ? await beacon.blob.text() : String(beacon.blob);
  registrar(
    "B3 sendBeacon: uma URL, um corpo, nenhum cabeçalho de credencial",
    enviouBeacon && chamadas.length === 1 && /\/api\/metricas\/eventos\/$/.test(beacon.url) && beacon.quantidade === 2,
    `url=${beacon?.url} · ${beacon?.quantidade} argumento(s) (url + corpo) · nenhum 3º header`
  );
  registrar(
    "B3 sendBeacon: corpo sem token e sem query string",
    !/token/i.test(corpoBeacon) && !corpoBeacon.includes("?"),
    corpoBeacon
  );
  registrar(
    "B3 sendBeacon: o corpo é o evento allowlisted (path sem query string)",
    JSON.parse(corpoBeacon).path === "/noticia/12",
    corpoBeacon
  );

  // Caminho sem `sendBeacon`: `fetch` e os cabeçalhos observados.
  definirNavigator({});
  let initVisto = null;
  let urlVista = "";
  globalThis.fetch = (url, init) => {
    urlVista = url;
    initVisto = init;
    return Promise.resolve({ ok: true });
  };
  analytics.enviarEvento({ tipo: "page_view", path: "/x", sessao: "s1-abcd" });
  const chavesCabecalho = Object.keys(initVisto?.headers ?? {});
  registrar(
    "B3 fetch: cabeçalho tem SÓ Content-Type (sem Authorization, sem token)",
    chavesCabecalho.length === 1 && chavesCabecalho[0] === "Content-Type",
    `headers = ${JSON.stringify(initVisto?.headers)}`
  );
  registrar(
    "B3 fetch: sem credentials: include e sem cabeçalho de sessão",
    !("credentials" in (initVisto ?? {})),
    `init = ${JSON.stringify({ ...initVisto, body: "<corpo>" })}`
  );
  registrar(
    "B3 destino é o backend do próprio portal (primeira parte), não um terceiro",
    /\/api\/metricas\/eventos\/$/.test(urlVista),
    urlVista
  );
  delete globalThis.fetch;

  // ---- B4: o consentimento é a única autorização ------------------------
  registrar(
    "B4 consentido() só existe a partir de permiteCategoria('analytics')",
    /permiteCategoria\s*\(\s*["']analytics["']\s*\)/.test(await readFile(path.join(dirFrontend, "lib", "analytics.ts"), "utf8")),
    "lib/analytics.ts::consentido -> permiteCategoria(\"analytics\")"
  );

  console.log("\nB) Estático, sobre os fontes de app/ components/ lib/:\n");
  let varridos = 0;
  const problemas = [];
  for (const dir of DIRETORIOS_VARRIDOS) {
    const arquivos = (await arquivosRecursivos(path.join(dirFrontend, dir))).filter((a) => EXTENSOES_FONTE.test(a));
    for (const arquivo of arquivos) {
      const fonte = removerComentarios(await readFile(arquivo, "utf8"));
      varridos += 1;
      const rel = path.relative(dirFrontend, arquivo);
      for (const [id, , regra] of REGRAS_ESTATICAS) {
        const r = regra(rel, fonte);
        if (!r.ok) problemas.push(`${id} ${rel}: ${r.detalhes}`);
      }
    }
  }
  registrar(
    "regras estáticas P1-10 em todos os fontes",
    problemas.length === 0,
    problemas.length === 0
      ? `${varridos} arquivo(s) varridos, 0 violação(ões)`
      : `${problemas.length} violação(ões):\n    - ${problemas.join("\n    - ")}`
  );

  rodarAutotestes();

  const falhas = autotestes.filter((a) => !a.ok).length;
  console.log(`\nResumo: ${varridos} fonte(s) varrido(s), ${autotestes.length} autoteste(s) (${falhas} falha(s)), ${violacoes.length} violação(ões).`);
  if (violacoes.length > 0) {
    console.error(`\n${violacoes.length} verificação(ões) em VIOLAÇÃO de P1-10 (eventos/analytics).`);
    process.exit(1);
  }
  console.log("\nP1-10 OK — nada externo sem consentimento; nenhum token e nenhuma query string no evento.");
}

main().catch((erro) => {
  console.error(`[VIOLAÇÃO] falha inesperada na verificação: ${erro?.message ?? String(erro)}`);
  process.exit(1);
});
