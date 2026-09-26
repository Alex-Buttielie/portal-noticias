#!/usr/bin/env node
/**
 * Guarda de regressão P1-09 — "Free mostra ads; Premium não; fallback Free sem ads".
 *
 * O projeto não tem runner de teste de componente (vitest/jest não estão na
 * base e dependência está fora do escopo deste run), então esta guarda age em
 * duas frentes:
 *
 *  A) COMPORTAMENTAL, sobre o código REAL: importa `lib/anuncios.ts` e
 *     `lib/analytics.ts` direto (Node 24 remove os tipos; um resolver local
 *     resolve import sem extensão, o mesmo truque de `testes/hooks.mjs`) e
 *     exercita `podeExibirAnuncio()` e `revogarSaidaAds()`. Isto é o que
 *     responde "o Premium vê anúncio?" e "revogar remove o script?".
 *
 *  B) ESTÁTICA, sobre os fontes: as condições de consentimento/Premium que a
 *     guarda comportamental não consegue provar sozinha (ordem da checagem,
 *     ausência de pré-carregamento no `<head>`, ausência de ID de cliente
 *     inventado).
 *
 * Cada regra estática é uma função pura `regra(caminho, fonte)` e tem
 * autoteste embutido com DOIS casos: um NEGATIVO (a regra precisa reprovar um
 * fonte quebrado sintético) e um de FALSO POSITIVO (a regra precisa ACEITAR um
 * fonte inocente que superficialmente parece suspeito). Uma guarda que nunca
 * falha não é guarda; uma guarda que falha em código innocento é ruído.
 *
 * Uso:  node scripts/verificar-consentimento-anuncios.mjs
 * Sai com 0 se tudo passa; 1 com a lista de violações.
 */
import { readdir, readFile } from "node:fs/promises";
import { registerHooks } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import fs from "node:fs";
import path from "node:path";

const dirScript = path.dirname(fileURLToPath(import.meta.url));
const dirFrontend = path.resolve(dirScript, "..");

// ---------------------------------------------------------------------------
// Resolver: o Next resolve `@/` e import sem extensão; o Node, não.
// Mesma abordagem de `testes/hooks.mjs`, embutida para o script continuar
// executável sozinho.
// ---------------------------------------------------------------------------
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

// `import()` de um `.ts` num pacote sem `"type": "module"` emite um aviso de
// reparse. Não dá para adicionar `"type": "module"` ao package.json (fora do
// escopo deste run), então o aviso é filtrado aqui — e SÓ ele: qualquer outro
// aviso continua passando, para a guarda não virar um encobrimento do CI.
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

/**
 * Remove comentários preservando strings e a contagem de linhas. Indispensável
 * porque a própria documentação deste projeto escreve "preconnect",
 * "googlesyndication" e "ca-pub-" ao explicar por que NÃO os usa — e uma
 * guarda que lesse comentário acusaria a si mesma.
 */
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

/** Hosts de anúncio/medição do Google, para varredura de fonte. */
const REGEX_HOST_EXTERNO =
  /(?:pagead2|tpc|securepubads|pagead)\.(?:googlesyndication\.com|doubleclick\.net)|googletagmanager\.com|google-analytics\.com|csi\.gstatic\.com/i;

// ---------------------------------------------------------------------------
// Regras estáticas (funções puras — autotestáveis)
// ---------------------------------------------------------------------------

/**
 * R1: nenhum arquivo pode referenciar host de anúncio/medição do Google sem
 * estar atrás de um portão de consentimento no mesmo arquivo.
 * Isenções: o módulo de decisão (`lib/anuncios.ts`) e o de eventos
 * (`lib/analytics.ts`), que só CLASSIFICAM host, não emitem nada.
 */
function regraPortaoDeConsentimento(caminho, fonte) {
  const base = path.basename(caminho);
  if (base === "anuncios.ts" || base === "analytics.ts") {
    return { ok: true, detalhes: "módulo de decisão/classificação (não emite saída externa)" };
  }
  if (!REGEX_HOST_EXTERNO.test(fonte)) {
    return { ok: true, detalhes: "nenhum host de anúncio/medição no código" };
  }
  const temPortao =
    /permiteCategoria\s*\(/.test(fonte) ||
    /consentiuAnuncio\s*\(/.test(fonte) ||
    /podeExibirAnuncio\s*\(/.test(fonte);
  return {
    ok: temPortao,
    detalhes: temPortao
      ? "host de anúncio referenciado atrás de portão de consentimento no mesmo arquivo"
      : `host de anúncio/medição referenciado SEM nenhum portão de consentimento no arquivo (primeira ocorrência na linha ${linhaDe(fonte, fonte.search(REGEX_HOST_EXTERNO))})`,
  };
}

/**
 * R2: o `<head>` do layout raiz não pode pré-carregar nada do Google de
 * anúncio. `preconnect`/`dns-prefetch` contam como saída externa: o
 * handshake TLS com o host do Google já entrega IP, hora e User-Agent ao
 * Google ANTES de qualquer consentimento, mesmo sem carregar byte de script.
 */
function regraHeadSemPrecarregamento(caminho, fonte) {
  if (path.basename(caminho) !== "layout.tsx") return { ok: true, detalhes: "não é layout" };
  const achados = [];
  if (REGEX_HOST_EXTERNO.test(fonte)) {
    achados.push(`host de anúncio/medição na linha ${linhaDe(fonte, fonte.search(REGEX_HOST_EXTERNO))}`);
  }
  for (const [rotulo, re] of [
    ["preconnect", /rel\s*=\s*["']preconnect["']/i],
    ["dns-prefetch", /rel\s*=\s*["']dns-prefetch["']/i],
    ["<link", /<link\b/i],
    ["<script src", /<script\b[^>]*\bsrc\s*=/i],
  ]) {
    const m = fonte.match(re);
    if (m) achados.push(`${rotulo} na linha ${linhaDe(fonte, m.index)}`);
  }
  return {
    ok: achados.length === 0,
    detalhes: achados.length === 0
      ? "layout raiz sem host de anúncio, sem preconnect/dns-prefetch, sem <link> e sem <script src>"
      : achados.join(" | "),
  };
}

/**
 * R3: o componente que injeta o `adsbygoogle.js` tem de ter as DUAS
 * condições — consentimento de publicidade E não-Premium. A checagem de
 * Premium é a que faltava no `develop`: o script era carregado para
 * Premium que tivesse consentido.
 */
function regraScriptExigeConsentimentoEPremium(caminho, fonte) {
  if (path.basename(caminho) !== "AdsScript.tsx") return { ok: true, detalhes: "não é AdsScript" };
  if (!REGEX_HOST_EXTERNO.test(fonte)) return { ok: true, detalhes: "não referencia host de anúncio" };
  const consentimento = /consentiuAnuncio\s*\(/.test(fonte) || /permiteCategoria\s*\(/.test(fonte);
  const premium = /usePremiumAtivo|premiumGeral/.test(fonte);
  const ausentes = [];
  if (!consentimento) ausentes.push("sem checagem de consentimento");
  if (!premium) ausentes.push("SEM checagem de Premium (Premium baixaria adsbygoogle.js)");
  return {
    ok: ausentes.length === 0,
    detalhes: ausentes.length === 0 ? "gate = consentimento && !premium" : ausentes.join(", "),
  };
}

/**
 * R4: o `AdsSlot` decide o Premium DENTRO do componente. Se a decisão fica só
 * no ponto de montagem, basta um `<AdsSlot />` esquecido numa página nova
 * para o Premium voltar a ver anúncio.
 */
function regraSlotDecidePremiumInterno(caminho, fonte) {
  if (path.basename(caminho) !== "AdsSlot.tsx") return { ok: true, detalhes: "não é AdsSlot" };
  const temHook = /usePremiumAtivo/.test(fonte);
  const temFuncao = /podeExibirAnuncio\s*\(/.test(fonte);
  const saiNoPremium = /if\s*\(\s*premiumGeral\s*\)\s*return null\s*;?/.test(fonte);
  const insAtrásDoPortão = /if\s*\(\s*podeExibir\s*\)/.test(fonte);
  const ausentes = [];
  if (!temHook) ausentes.push("não consulta usePremiumAtivo");
  if (!temFuncao) ausentes.push("não usa podeExibirAnuncio");
  if (!saiNoPremium) ausentes.push("não devolve null para Premium (deixaria buraco de PUBLICIDADE)");
  if (!insAtrásDoPortão) ausentes.push("<ins class=adsbygoogle> não está atrás de `if (podeExibir)`");
  return {
    ok: ausentes.length === 0,
    detalhes: ausentes.length === 0 ? "Premium resolvido no componente" : ausentes.join(", "),
  };
}

/**
 * R5: revogação tem de derrubar a saída já injetada. Sem isso, revogar o
 * consentimento tirava o `<ins>` da árvore React mas deixava o `<script>` do
 * AdSense vivo no DOM (`next/script` com `lazyOnload` não tem cleanup de
 * unmount) — o tracking continuava depois da revogação.
 */
function regraRevogacaoDerrubaSaida(caminho, fonte) {
  if (path.basename(caminho) !== "AdsScript.tsx") return { ok: true, detalhes: "não é AdsScript" };
  const chama = /revogarSaidaAds\s*\(/.test(fonte);
  const guardada = /if\s*\(\s*!podeCarregar\s*\)\s*revogarSaidaAds\s*\(\s*\)\s*;?/.test(fonte);
  return {
    ok: chama && guardada,
    detalhes: chama && guardada
      ? "revogação remove script/link/ins e a fila global do AdSense"
      : !chama
        ? "nunca revoga a saída de anúncio já injetada (tracking sobrevive à revogação)"
        : "revoga sem estar guardada por `!podeCarregar`",
  };
}

/**
 * R6: nenhum ID de cliente de AdSense (`ca-pub-…`) ou de medição (`G-…`)
 * escrito à mão no frontend. ID inventado é conta de outra pessoa; e o ID
 * real é credencial de configuração, não de código-fonte. Este é o guard que
 * impede que alguém "feche a validação" com um ID falso.
 */
function regraSemIdDeClienteNoCodigo(caminho, fonte) {
  const achados = [];
  const caPub = /["'`]ca-pub-\d{6,}["'`]/.exec(fonte);
  if (caPub) achados.push(`ID AdSense literal na linha ${linhaDe(fonte, caPub.index)}`);
  const gId = /["'`]G-[A-Z0-9]{6,}["'`]/.exec(fonte);
  if (gId) achados.push(`ID de medição GA4 literal na linha ${linhaDe(fonte, gId.index)}`);
  const awId = /["'`]AW-\d{6,}["'`]/.exec(fonte);
  if (awId) achados.push(`ID de campanha AdWords literal na linha ${linhaDe(fonte, awId.index)}`);
  return {
    ok: achados.length === 0,
    detalhes: achados.length === 0 ? "publisher ID e measurement ID vêm de process.env" : achados.join(" | "),
  };
}

const REGRAS_ESTATICAS = [
  ["R1", "todo host de anúncio/medição atrás de portão de consentimento", regraPortaoDeConsentimento],
  ["R2", "`<head>` do layout raiz sem pré-carregamento de anúncio", regraHeadSemPrecarregamento],
  ["R3", "AdsScript exige consentimento E não-Premium", regraScriptExigeConsentimentoEPremium],
  ["R4", "AdsSlot decide o Premium dentro do componente", regraSlotDecidePremiumInterno],
  ["R5", "revogação derruba a saída de anúncio já injetada", regraRevogacaoDerrubaSaida],
  ["R6", "nenhum ID de cliente AdSense/GA4 literal no código", regraSemIdDeClienteNoCodigo],
];

// ---------------------------------------------------------------------------
// Autotestes das regras estáticas
// ---------------------------------------------------------------------------

function rodarAutotestes() {
  console.log("\nAutotestes das regras (negativo = precisa reprovar; falso positivo = precisa aceitar):");

  // R1
  registrarAutoteste(
    "R1 negativo: script do AdSense sem portão de consentimento",
    regraPortaoDeConsentimento("components/X.tsx", 'return <Script src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" />;').ok === false,
    "reprovado como deve"
  );
  registrarAutoteste(
    "R1 falso positivo: mesmo script COM portão de consentimento",
    regraPortaoDeConsentimento("components/X.tsx", 'if (!permiteCategoria("personalizacao")) return null;\nreturn <Script src="https://pagead2.googlesyndication.com/x.js" />;').ok === true
  );
  registrarAutoteste(
    "R1 falso positivo: menção a googlesyndication só em comentário",
    regraPortaoDeConsentimento("components/X.tsx", '// não usamos googlesyndication.com antes do consentimento\nexport const a = 1;').ok === true
  );
  registrarAutoteste(
    "R1 isenta o módulo de decisão",
    regraPortaoDeConsentimento("lib/anuncios.ts", 'export const HOSTS_ANUNCIO = ["pagead2.googlesyndication.com"];').ok === true
  );

  // R2
  registrarAutoteste(
    "R2 negativo: preconnect do AdSense no layout",
    regraHeadSemPrecarregamento("app/layout.tsx", '<head><link rel="preconnect" href="https://pagead2.googlesyndication.com" /></head>').ok === false,
    "reprovado como deve (preconnect conta como saída externa)"
  );
  registrarAutoteste(
    "R2 negativo: dns-prefetch no layout",
    regraHeadSemPrecarregamento("app/layout.tsx", '<head><link rel="dns-prefetch" href="//www.googletagmanager.com" /></head>').ok === false
  );
  registrarAutoteste(
    "R2 falso positivo: layout real (AdsScript sem host no markup)",
    regraHeadSemPrecarregamento("app/layout.tsx", '<head><script dangerouslySetInnerHTML={{ __html: S }} /><JsonLd /><AdsScript /></head>').ok === true
  );
  registrarAutoteste(
    "R2 falso positivo: layout de página que não é o raiz",
    regraHeadSemPrecarregamento("app/planos/page.tsx", '<head><link rel="preconnect" href="https://fonts.googleapis.com" /></head>').ok === true,
    "regra só vale para o layout raiz"
  );

  // R3
  const adsScriptBase = 'export function AdsScript(){ return <Script src="https://pagead2.googlesyndication.com/x.js" />; }';
  registrarAutoteste("R3 negativo: script com consentimento mas SEM Premium", regraScriptExigeConsentimentoEPremium("components/AdsScript.tsx", 'const x = consentiuAnuncio();' + adsScriptBase).ok === false);
  registrarAutoteste("R3 negativo: script sem nenhum gate", regraScriptExigeConsentimentoEPremium("components/AdsScript.tsx", adsScriptBase).ok === false);
  registrarAutoteste(
    "R3 falso positivo: script com os dois gates",
    regraScriptExigeConsentimentoEPremium("components/AdsScript.tsx", 'const x = consentiuAnuncio(); const { liberado } = usePremiumAtivo();' + adsScriptBase).ok === true
  );
  registrarAutoteste(
    "R3 não acusa componente que não fala de anúncio",
    regraScriptExigeConsentimentoEPremium("components/Rodape.tsx", 'export function Rodape(){ return <footer>ok</footer>; }').ok === true
  );

  // R4
  registrarAutoteste(
    "R4 negativo: slot que só confia no chamador (baseline do develop)",
    regraSlotDecidePremiumInterno("components/AdsSlot.tsx", 'useEffect(()=>setPodeExibir(permiteCategoria("personalizacao")),[]);if(ADSENSE_CLIENT_ID&&slot&&podeExibir)return <ins className="adsbygoogle"/>;').ok === false,
    "reprovado como deve"
  );
  registrarAutoteste(
    "R4 negativo: slot que consulta o Premium mas não some para Premium",
    regraSlotDecidePremiumInterno("components/AdsSlot.tsx", 'usePremiumAtivo(); podeExibirAnuncio({}); if (podeExibir) return <ins/>;').ok === false,
    "reprovado como deve (deixaria o buraco de PUBLICIDADE)"
  );
  registrarAutoteste(
    "R4 falso positivo: slot completo",
    regraSlotDecidePremiumInterno(
      "components/AdsSlot.tsx",
      'usePremiumAtivo(); const r = podeExibirAnuncio({}); if (premiumGeral) return null; if (podeExibir) return <ins className="adsbygoogle"/>;'
    ).ok === true
  );

  // R5
  registrarAutoteste("R5 negativo: AdsScript sem revogação alguma", regraRevogacaoDerrubaSaida("components/AdsScript.tsx", 'export function AdsScript(){ return null; }').ok === false);
  registrarAutoteste(
    "R5 negativo: revoga sem guardar",
    regraRevogacaoDerrubaSaida("components/AdsScript.tsx", "revogarSaidaAds();").ok === false
  );
  registrarAutoteste(
    "R5 falso positivo: revogação guardada",
    regraRevogacaoDerrubaSaida("components/AdsScript.tsx", "if (!podeCarregar) revogarSaidaAds();").ok === true
  );

  // R6
  registrarAutoteste("R6 negativo: publisher ID AdSense na mão", regraSemIdDeClienteNoCodigo("lib/x.ts", 'const ID = "ca-pub-1234567890123456";').ok === false);
  registrarAutoteste("R6 negativo: measurement ID GA4 na mão", regraSemIdDeClienteNoCodigo("lib/x.ts", 'const M = "G-ABC123XYZ";').ok === false);
  registrarAutoteste(
    "R6 falso positivo: ID vindo de process.env",
    regraSemIdDeClienteNoCodigo("lib/anuncios.ts", 'export const ADSENSE_CLIENT_ID = process.env.NEXT_PUBLIC_ADSENSE_CLIENT_ID || "";').ok === true
  );
  registrarAutoteste(
    "R6 falso positivo: a PALAVRA ca-pub em comentário/d explained",
    regraSemIdDeClienteNoCodigo("lib/anuncios.ts", '// o formato do publisher ID é ca-pub-1234567890123456 e nunca vai no fonte').ok === true
  );
}

// ---------------------------------------------------------------------------
// DOM mínimo para exercitar revogarSaidaAds() contra o código real
// ---------------------------------------------------------------------------

/**
 * Só implementa o que o seletor de `revogarSaidaAds` usa: tag, `.classe`,
 * `[attr]` e `[attr*="valor"]`. Não é um DOM geral — é o suficiente para que a
 * lista de seletores do módulo (que é o que está sob teste) seja exercitada de
 * verdade: trocar um seletor em `lib/anuncios.ts` muda o resultado aqui.
 */
function criarNo(tag, atributos = {}, classes = []) {
  return {
    tagName: tag.toUpperCase(),
    atributos,
    classes,
    parentNode: null,
    removido: false,
    removeChild(filho) {
      filho.removido = true;
      const pai = this;
      pai.filhos = (pai.filhos || []).filter((n) => n !== filho);
    },
  };
}

function criaDocumentoFalso(nos) {
  const raiz = criarNo("html");
  raiz.filhos = [...nos];
  for (const no of nos) no.parentNode = raiz;
  return {
    corpo: raiz,
    // Um nó já removido some da árvore, então um `querySelectorAll` posterior
    // não o encontra mais — é o que um DOM real faz, e é o que impede a mesma
    // nó de ser contada duas vezes por dois seletores que casam com ele.
    querySelectorAll(seletor) {
      // Um `.` ou uma letra dentro do VALOR de um atributo (`[src*="…com"]`)
      // não é seletor. Um parser de CSS não se confunde com isso; este shim
      // precisa não se confundir também, senão todo seletor com domínio
      // casaria com a classe `com`.
      const fora = seletor.replace(/"[^"]*"/g, '""');
      const tag = fora.match(/^([a-z0-9]+)/i)?.[1];
      const classe = fora.match(/\.([a-z0-9_-]+)/i)?.[1];
      const atributoIgual = seletor.match(/\[([a-z-]+)\]$/i)?.[1];
      const atributoContem = seletor.match(/\[([a-z-]+)\*="([^"]+)"\]/i);
      return raiz.filhos.filter((no) => {
        if (tag && no.tagName !== tag.toUpperCase()) return false;
        if (classe && !no.classes.includes(classe)) return false;
        if (atributoIgual && !(atributoIgual in no.atributos)) return false;
        if (atributoContem) {
          const valor = no.atributos[atributoContem[1]];
          if (typeof valor !== "string" || !valor.includes(atributoContem[2])) return false;
        }
        return true;
      });
    },
  };
}

// ---------------------------------------------------------------------------

async function main() {
  console.log("P1-09 — Free mostra ads; Premium não; fallback Free sem ads\n");
  console.log("A) Comportamental, sobre lib/anuncios.ts real:\n");

  // ---- B1: a tabela-verdade do Premium -------------------------------------
  const anuncios = await import(path.join(dirFrontend, "lib", "anuncios.ts"));
  const comId = { temPublisherId: true };
  const semId = { temPublisherId: false };
  const casos = [
    ["Free + consentimento + publisher ID => ANÚNCIO", { consentiu: true, premium: false, ...comId }, true],
    ["Free + consentimento SEM publisher ID => nada", { consentiu: true, premium: false, ...semId }, false],
    ["Free SEM consentimento => nada (nada sai da máquina)", { consentiu: false, premium: false, ...comId }, false],
    ["PREMIUM + consentimento => NADA (P1-09)", { consentiu: true, premium: true, ...comId }, false],
    ["FALLBACK FREE (status Premium desconhecido) + consentimento => NADA", { consentiu: true, premium: true, ...comId }, false],
    ["Premium sem consentimento => nada", { consentiu: true, premium: true, ...semId }, false],
  ];
  for (const [nome, entrada, esperado] of casos) {
    const obtido = anuncios.podeExibirAnuncio(entrada);
    registrar(`B1 ${nome}`, obtido === esperado, `podeExibirAnuncio(${JSON.stringify(entrada)}) = ${obtido}`);
  }

  // ---- B2: o status desconhecido do Premium conta como Premium ------------
  // `usePremiumAtivo` devolve `liberado: ativo !== true` (fail-open). A prova de
  // que o fallback Free NÃO mostra ads é esta: o valor que o hook devolve no
  // estado `null` (carregando/erro) é `true`, e `true` é o `premium` de
  // `podeExibirAnuncio`.
  const fontePremium = await readFile(path.join(dirFrontend, "lib", "premium.ts"), "utf8");
  const failOpen = /liberado:\s*ativo\s*!==\s*true/.test(removerComentarios(fontePremium));
  registrar(
    "B2 usePremiumAtivo é fail-open para o Premium (fallback Free sem ads)",
    failOpen && anuncios.podeExibirAnuncio({ consentiu: true, premium: true, temPublisherId: true }) === false,
    failOpen ? "`liberado: ativo !== true` — status desconhecido/erro => sem anúncio" : "liberado não é fail-open"
  );

  // ---- B3: revogação remove a saída já injetada ---------------------------
  const script = criarNo("script", { src: "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-x" });
  const link = criarNo("link", { href: "https://csi.gstatic.com/ad.css" });
  const ins = criarNo("ins", { "data-ad-client": "ca-pub-x" }, ["adsbygoogle"]);
  const iframe = criarNo("iframe", { src: "https://googleads.g.doubleclick.net/x.html" });
  const proprio = criarNo("script", { src: "/_next/static/chunks/main.js" });
  const docFalso = criaDocumentoFalso([script, link, ins, iframe, proprio]);
  globalThis.document = docFalso;
  globalThis.window = { adsbygoogle: [{ filled: true }] };
  const removidos = anuncios.revogarSaidaAds();
  const restantes = docFalso.corpo.filhos ?? [];
  registrar(
    "B3 revogação remove <script>/<link>/<ins>/<iframe> de anúncio do DOM",
    removidos === 4 && restantes.length === 1 && restantes[0] === proprio,
    `${removidos} nó(s) removido(s); sobrou ${restantes.length} (o script próprio do site)`
  );
  registrar(
    "B3 revogação apaga a fila global do AdSense (push tardio não acha slot)",
    globalThis.window.adsbygoogle === undefined,
    "window.adsbygoogle = undefined"
  );

  // ---- B4: consentimento é a única coisa que autoriza ---------------------
  registrar(
    "B4 a categoria de consentimento do anúncio é `personalizacao`",
    anuncios.CATEGORIA_CONSENTIMENTO_ANUNCIO === "personalizacao",
    `CATEGORIA_CONSENTIMENTO_ANUNCIO = ${JSON.stringify(anuncios.CATEGORIA_CONSENTIMENTO_ANUNCIO)}`
  );

  // ---- B5: nenhum host de medição (GA4) usado ----------------------------
  registrar(
    "B5 nenhum host de medição (GA4/GTM) é emitido — pendente de conta",
    anuncios.GA4_NAO_IMPLEMENTADO === true && anuncios.HOSTS_MEDICAO.length > 0,
    `GA4_NAO_IMPLEMENTADO=${anuncios.GA4_NAO_IMPLEMENTADO}; hosts de medição declarados e NÃO usados: ${anuncios.HOSTS_MEDICAO.join(", ")}`
  );

  // ---- B) Estático sobre os fontes ---------------------------------------
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
    "regras estáticas P1-09 em todos os fontes",
    problemas.length === 0,
    problemas.length === 0 ? `${varridos} arquivo(s) varridos, 0 violação(ões)` : `${problemas.length} violação(ões):\n    - ${problemas.join("\n    - ")}`
  );

  rodarAutotestes();

  const falhasAutoteste = autotestes.filter((a) => !a.ok).length;
  console.log(
    `\nResumo: ${varridos} fonte(s) varrido(s), ${autotestes.length} autoteste(s) (${falhasAutoteste} falha(s)), ${violacoes.length} violação(ões).`
  );
  if (violacoes.length > 0) {
    console.error(`\n${violacoes.length} verificação(ões) em VIOLAÇÃO de P1-09 (AdSense/Premium).`);
    process.exit(1);
  }
  console.log("\nP1-09 OK — nada externo antes do consentimento, Premium sem anúncios, fallback Free sem anúncios.");
}

main().catch((erro) => {
  console.error(`[VIOLAÇÃO] falha inesperada na verificação: ${erro?.message ?? String(erro)}`);
  process.exit(1);
});
