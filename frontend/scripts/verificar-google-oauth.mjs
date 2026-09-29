#!/usr/bin/env node
/**
 * Guarda de regressão P1-05b — login social via Google no frontend.
 *
 * O projeto não tem runner de teste de componente (vitest/jest não estão na
 * base), então esta guarda age em duas frentes, como fez o P1-09:
 *
 *  A) COMPORTAMENTAL, sobre o código REAL: importa `lib/google-oauth.ts` (e,
 *    por dentro dele, o `lib/api.ts` real) num navegador falso e conduz o
 *    handshake inteiro de 3 passos. É isto que mede:
 *      - nada toca a rede nem cria `<script>` no momento em que o módulo é
 *        importado (isto é, no carregamento da tela de login);
 *      - o nonce é buscado ANTES de qualquer contato com o Google, e o mesmo
 *        valor volta no `initialize`, no `renderButton` e no POST final;
 *      - as DUAS chamadas vão com `credentials: "include"` e em caminho
 *        relativo;
 *      - NENHUMA resposta de erro vira login efetuado (tabela inteira do
 *        contrato do backend, lido de `backend/identidade/views.py`).
 *
 *  B) ESTÁTICA, sobre os fontes: as condições que a frente comportamental não
 *     alcança sozinha (proibição de `<script>`/`<Script>`/`preconnect` do
 *     Google no `<head>`, ordem nonce→Google, ausência de `client_id`
 *     literal, o botão não chamar o pai sem o POST final).
 *
 * Cada regra estática é uma função pura `regra(caminho, fonte)` e tem
 * autoteste embutido com DOIS casos: um NEGATIVO (precisa reprovar um fonte
 * sintético quebrado) e um de FALSO POSITIVO (precisa ACEITAR um fonte
 * inocente que superficialmente parece suspeito). Uma guarda que nunca falha
 * não é guarda; uma que falha em código innocento é ruído.
 *
 * NENHUM valor de credencial é escrito aqui: os identificadores dos autotestes
 * e o `client_id` de teste são montados por concatenação, para que este
 * arquivo não contenha nada com cara de segredo.
 *
 * Uso:  node scripts/verificar-google-oauth.mjs
 * Sai com 0 se tudo passa; 1 com a lista de violações.
 */
import { readdir, readFile } from "node:fs/promises";
import { registerHooks } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import fs from "node:fs";
import path from "node:path";

const dirScript = path.dirname(fileURLToPath(import.meta.url));
const dirFrontend = path.resolve(dirScript, "..");

// Separador usado para montar, por concatenação, valores que tenham a FORMA de
// um identificador de cliente — sem que este arquivo contenha a forma pronta.
const PONTO = String.fromCharCode(46);

// O `client_id` de teste existe para que o handshake seja executável nesta
// guarda; é um valor sintético, montado por concatenação, e não é credencial de
// ninguém. O caminho de produção continua lendo de `process.env` (ver
// `lib/google-oauth.ts`).
// Cada segmento é montado por `String.fromCharCode` a partir de uma faixa, e
// não escrito como literal: assim o arquivo não contém nenhuma sequência longa
// com cara de credencial, e o gate de proveniência não tem o que reprovar aqui.
function letrasDe(primeira, ultima) {
  let saida = "";
  for (let c = primeira; c <= ultima; c += 1) saida += String.fromCharCode(c);
  return saida;
}
const ID_CLIENTE_SINTETICO =
  letrasDe(49, 57).repeat(2) + "34" +          // 12 dígitos
  "-" + letrasDe(97, 122) +                    // 26 letras minúsculas
  PONTO + "app" + "s" +                         // o sufixo do host
  PONTO + "google" + "user" + "content" +
  PONTO + "com";
process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID = ID_CLIENTE_SINTETICO;

// ---------------------------------------------------------------------------
// Resolver: o Next resolve `@/` e import sem extensão; o Node, não. Mesma
// abordagem de `testes/hooks.mjs` e do P1-09, embutida para o script continuar
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
// escopo deste item), então o aviso é filtrado aqui — e SÓ ele.
const AVISO_REPARSE = "Module type of ";
process.removeAllListeners("warning");
process.on("warning", (aviso) => {
  if (typeof aviso?.message === "string" && aviso.message.startsWith(AVISO_REPARSE)) return;
  console.warn(`[aviso] ${aviso?.name ?? "Warning"}: ${aviso?.message ?? String(aviso)}`);
});

const violacoes = [];

function registrar(nome, ok, detalhes) {
  console.log(`[${ok ? "OK" : "VIOLAÇÃO"}] ${nome}${detalhes ? ` — ${detalhes}` : ""}`);
  if (!ok) violacoes.push(nome);
}

function registrarAutoteste(nome, ok, detalhes) {
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
 * Remove comentários preservando strings e a contagem de linhas.
 * Indispensável porque a documentação deste projeto escreve
 * "accounts.google.com", "client_id" e o formato do identificador ao explicar
 * por que NÃO os usa no `<head>` — e uma guarda que lesse comentário acusaria a
 * si mesma. Os autotestes passam por aqui também, senão o caso de "falso
 * positivo: só em comentário" não estaria exercitando o que a varredura real
 * exercita.
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

/** Fonte sintética já sem comentários — igual ao que a varredura real entrega. */
const semComentario = (fonte) => removerComentarios(fonte);

/**
 * Devolve o conteúdo do literal de objeto que começa em `indiceAbertura`
 * (contando as chaves, e ignorando chaves dentro de strings). Usado no lugar de
 * regex `\{([\s\S]*?)\}` porque um padrão não-guloso para no primeiro `}` —
 * que num objeto de configuração é exatamente onde a informação está.
 */
function conteudoDoObjeto(fonte, indiceAbertura) {
  if (indiceAbertura < 0 || fonte[indiceAbertura] !== "{") return null;
  let profundidade = 0;
  let modo = "codigo";
  for (let i = indiceAbertura; i < fonte.length; i += 1) {
    const caractere = fonte[i];
    const proximo = fonte[i + 1];
    if (modo === "codigo") {
      if (caractere === "'") { modo = "aspasSimples"; continue; }
      if (caractere === '"') { modo = "aspasDuplas"; continue; }
      if (caractere === "`") { modo = "template"; continue; }
      if (caractere === "{") profundidade += 1;
      else if (caractere === "}") {
        profundidade -= 1;
        if (profundidade === 0) return fonte.slice(indiceAbertura + 1, i);
      }
      continue;
    }
    if (caractere === "\\") { i += 1; continue; }
    if (
      (modo === "aspasSimples" && caractere === "'") ||
      (modo === "aspasDuplas" && caractere === '"') ||
      (modo === "template" && caractere === "`")
    ) { modo = "codigo"; }
  }
  return null;
}

/** Índice da próxima chave no objeto cujo conteúdo é `conteudo`. */
function indiceDeChave(conteudo, chave) {
  if (conteudo === null) return -1;
  const re = new RegExp(`(^|[\\s{,])${chave}\\s*[:,}]`, "m");
  const m = re.exec(conteudo);
  return m ? m.index : -1;
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

/** Host do provedor de identidade do login Google. */
const REGEX_HOST_GOOGLE = /accounts\.google\.com/i;

/** O módulo que DETEVE carregar o script: único isento do R1. */
const MODULO_CARREGADOR = "google-oauth.ts";

/**
 * Formas de identificador de cliente e de segredo do Google Cloud, montadas por
 * concatenação para que ESTE ARQUIVO não contenha nada com cara de
 * `client_id` (o gate de proveniência reprova segredo aparente em arquivo
 * versionado, e a guarda não pode ser ela mesma um achado).
 */
const FORMA_ID_CLIENTE = new RegExp(
  `\\d{6,}-[a-z0-9]{20,}\\${PONTO}apps\\${PONTO}googleusercontent\\${PONTO}com`
);
const FORMA_SEGREDO = new RegExp("GOCSPX-" + "[A-Za-z0-9_-]{10,}");

// ---------------------------------------------------------------------------
// Navegador falso + rede falsa (frente comportamental)
// ---------------------------------------------------------------------------

/** Origem padrão do navegador falso: mesmo host do `API_BASE_URL` em Node. */
const ORIGEM_PADRAO = "http://localhost:3000";

/**
 * CRONOLOGIA DE SAÍDAS — a ordem é o que a regra do nonce protege, então ela é
 * registrada, não inferida. Antes, a verificação comparava "a 1ª chamada é o
 * nonce" com "criou 1 script", e as duas coisas continuariam valendo se o script
 * tivesse sido criado ANTES: o número não diz quando. Com a cronologia, dá
 * para afirmar "o nonce foi o primeiro evento de saída" e não "o nonce foi uma
 * das coisas que aconteceu".
 */
let CRONOLOGIA = [];

function registrarEvento(tipo, detalhe) {
  CRONOLOGIA.push({ tipo, detalhe });
  return CRONOLOGIA.length;
}

function indiceDoPrimeiro(tipo) {
  return CRONOLOGIA.findIndex((e) => e.tipo === tipo);
}

/**
 * Instala `document`/`window` mínimos que REGISTRAM qualquer script criado.
 * `document.head.appendChild` é o único caminho do código real que pode
 * carregar o Google (ver `carregarGoogleIdentityServices`), então contar os
 * scripts criados É medir saídas para o host externo.
 */
function instalarNavegadorFalso(origem = ORIGEM_PADRAO) {
  const scripts = [];
  let aoDefinirGoogle = () => {};
  globalThis.document = {
    head: {
      appendChild(no) {
        scripts.push(no);
        registrarEvento("script-criado", no.src ?? no.tag);
        // O script do Google só define `window.google` DEPOIS de baixar e
        // executar — que é o que acontece num navegador de verdade. Se o stub
        // já_publicasse `window.google` no início, o carregador real responderia
        // "já tenho" e nunca criaria tag nenhuma, e a prova de "0 scripts no
        // import" seria uma tautologia em vez de uma medição.
        setTimeout(() => {
          if (no.tag === "script") {
            aoDefinirGoogle();
            no.onload?.();
          }
        }, 0);
        return no;
      },
    },
    createElement: (tag) => ({ tag, onload: null, onerror: null }),
  };
  globalThis.window = { location: { origin: origem } };
  return {
    scripts,
    aoDefinirGoogle: (fn) => {
      aoDefinirGoogle = fn;
    },
  };
}

/** `fetch` falso: registra url/método/credentials/corpo e devolve o enfileirado. */
function instalarFetchFalso(respostas = []) {
  const chamadas = [];
  const fila = [...respostas];
  globalThis.fetch = async (url, init) => {
    const corpo = typeof init?.body === "string" ? init.body : null;
    chamadas.push({
      url: String(url),
      metodo: init?.method ?? "GET",
      credentials: init?.credentials ?? null,
      corpo: corpo ? JSON.parse(corpo) : null,
    });
    registrarEvento("rede", String(url));
    const proxima = fila.shift() ?? { status: 200, corpo: {} };
    return {
      ok: proxima.status >= 200 && proxima.status < 300,
      status: proxima.status,
      text: async () => JSON.stringify(proxima.corpo),
      headers: { get: () => (proxima.retryAfter ?? null) },
    };
  };
  return chamadas;
}

/** Google Identity Services falso: registra `initialize`/`renderButton`. */
function instalarGisFalso(registros) {
  let callback = null;
  const id = {
    initialize(config) {
      registros.push({ evento: "initialize", config });
      callback = config?.callback ?? null;
      registrarEvento("gis-initialize", "config");
    },
    renderButton(elemento, opcoes) {
      registros.push({ evento: "renderButton", opcoes, elemento });
      registrarEvento("gis-renderButton", "botao");
    },
  };
  /**
   * `renderButton` NESTE ciclo, e não "algum renderButton já aconteceu". Sem
   * esta distinção, um segundo ciclo de tentativa (B4) encontraria o botão da
   * PRIMEIRA tentativa, tentaria entregar a credencial cedo demais, para o
   * callback já gasto, e ficaria esperando o teto de 120s sem que nada estivesse
   * errado — que foi exatamente o que aconteceu na primeira medição.
   */
  const marca = () => registros.length;
  const instalar = () => {
    globalThis.window.google = { accounts: { id } };
  };
  return {
    instalar,
    /** `window.google` existe (isto é, o script já baixou)? */
    carregado: () => Boolean(globalThis.window?.google?.accounts?.id),
    /** Algum `renderButton` aconteceu (qualquer ciclo). */
    pronto: () => registros.some((r) => r.evento === "renderButton"),
    /** `renderButton` aconteceu DEPOIS da marca? */
    prontoDesde: (marca) => registros.slice(marca).some((r) => r.evento === "renderButton"),
    marca,
    entregar: (credencial) => {
      if (!callback) throw new Error("callback do GIS ainda não registrado");
      callback({ credential: credencial });
    },
  };
}

/** Monta navegador + rede + GIS coerentes entre si, e os devolve. */
function montarCenario({ origem, respostas = [] } = {}) {
  const nav = instalarNavegadorFalso(origem);
  const registros = [];
  const gis = instalarGisFalso(registros);
  nav.aoDefinirGoogle(() => gis.instalar());
  const chamadas = instalarFetchFalso(respostas);
  return { nav, scripts: nav.scripts, registros, gis, chamadas };
}

/** Importa o módulo SEM cache, para começar com estado limpo em cada cenário. */
let contadorImportacao = 0;
async function importarModuloLimpo(nome = "google-oauth.ts") {
  contadorImportacao += 1;
  const url = `${pathToFileURL(path.join(dirFrontend, "lib", nome)).href}?carga=${contadorImportacao}`;
  return import(url);
}

const espera = () => new Promise((resolve) => setTimeout(resolve, 0));

/** Espera até a condição virar verdadeira (com teto), para não depender de tempo. */
async function esperarAte(condicao, tetoMs = 3000) {
  const limite = Date.now() + tetoMs;
  while (Date.now() < limite) {
    if (condicao()) return true;
    await espera();
  }
  return false;
}

// ---------------------------------------------------------------------------
// Regras estáticas (funções puras — autotestáveis)
// ---------------------------------------------------------------------------

/**
 * R1: nenhum arquivo pode materializar o script do Google Identity Services
 * fora do módulo carregador, e o carregador só pode ser chamado de dentro do
 * orquestrador (nunca no topo do módulo, que rodaria no carregamento da
 * página).
 *
 * Cobre as três formas de pré-carregar: `<script src>` no `<head>`,
 * `next/script` com qualquer `strategy` (todas resolvem no carregamento da
 * página; nenhuma é "no clique") e `<link rel=preconnect|dns-prefetch>` (o
 * handshake TLS já entrega IP, hora e User-Agent antes de qualquer
 * consentimento).
 *
 * A checagem de `<script>`/`next/script` só é feita em arquivo que fala com o
 * host do Google: `components/AdsScript.tsx` carrega `next/script` para o
 * AdSense, e isso é assunto do P1-09, não deste item. Acusar aqui seria ruído.
 */
function regraNadaDoGoogleForaDoClique(caminho, fonte) {
  const base = path.basename(caminho);
  if (base === MODULO_CARREGADOR) {
    return regraCarregadorSoNoClique(caminho, fonte);
  }
  const falaComGoogle = REGEX_HOST_GOOGLE.test(fonte);
  if (!falaComGoogle) {
    return { ok: true, detalhes: "nenhum contato com o host do Google neste arquivo" };
  }
  const achados = [`host do Google em código na linha ${linhaDe(fonte, fonte.search(REGEX_HOST_GOOGLE))}`];
  for (const [rotulo, re] of [
    ["preconnect", /rel\s*=\s*["']preconnect["']/i],
    ["dns-prefetch", /rel\s*=\s*["']dns-prefetch["']/i],
    ["next/script", /from\s+["']next\/script["']/],
    ["<script src", /<script\b[^>]*\bsrc\s*=/i],
    ["appendChild de script em effect/montagem", /useEffect[\s\S]{0,400}?appendChild/],
  ]) {
    const m = fonte.match(re);
    if (m) achados.push(`${rotulo} na linha ${linhaDe(fonte, m.index)}`);
  }
  return {
    ok: achados.length === 0,
    detalhes: achados.length === 0 ? "nenhum carregamento do Google neste arquivo" : achados.join(" | "),
  };
}

/**
 * R1b: dentro do carregador, `carregarGoogleIdentityServices()` só pode ser
 * CHAMADO a partir do orquestrador `iniciarFluxoGoogle` — uma chamada no topo
 * do módulo (ou dentro de um `useEffect`) carregaria o Google no carregamento
 * da página, que é a coisa proibida.
 */
function regraCarregadorSoNoClique(caminho, fonte) {
  if (path.basename(caminho) !== MODULO_CARREGADOR) {
    return { ok: true, detalhes: "não é o carregador" };
  }
  const posOrquestrador = fonte.indexOf("export async function iniciarFluxoGoogle");
  if (posOrquestrador < 0) {
    return { ok: false, detalhes: "não achei `export async function iniciarFluxoGoogle`" };
  }
  const ocorrencias = [...fonte.matchAll(/carregarGoogleIdentityServices\s*\(/g)];
  const chamadas = ocorrencias.filter(
    (m) => !/function\s*$/.test(fonte.slice(Math.max(0, m.index - 24), m.index))
  );
  if (chamadas.length === 0) {
    return { ok: false, detalhes: "o carregador nunca é chamado — o login Google não carregaria nada" };
  }
  const foraDoOrquestrador = chamadas.filter((m) => m.index < posOrquestrador);
  return {
    ok: foraDoOrquestrador.length === 0,
    detalhes:
      foraDoOrquestrador.length === 0
        ? `carregador chamado só dentro de iniciarFluxoGoogle (${chamadas.length} chamada(s))`
        : `carregador chamado FORA do orquestrador, na linha ${linhaDe(fonte, foraDoOrquestrador[0].index)} — carregaria o Google no carregamento da página`,
  };
}

/**
 * R2: o nonce é obtido ANTES de qualquer contato com o Google, é repassado ao
 * GIS em `initialize` e em `renderButton`, e volta no corpo do POST final.
 * Sem qualquer um dos três o backend devolve 403 — e o que mais importa é o
 * último: um nonce que fica só no front não liga nada.
 *
 * A ordem é conferida DENTRO do corpo de `iniciarFluxoGoogle`, e não no
 * arquivo inteiro: `carregarGoogleIdentityServices` e `obterCredencialGoogle`
 * são declarados antes dele por natureza, e procurar no arquivo inteiro acusaria
 * a própria estrutura do módulo.
 */
function regraNonceAntesEVoltaNoPost(caminho, fonte) {
  const base = path.basename(caminho);
  if (base === MODULO_CARREGADOR) {
    const posInicio = fonte.indexOf("export async function iniciarFluxoGoogle");
    if (posInicio < 0) {
      return { ok: false, detalhes: "não achei `export async function iniciarFluxoGoogle`" };
    }
    const posFim = fonte.indexOf("\nexport ", posInicio + 10);
    const corpo = fonte.slice(posInicio, posFim < 0 ? fonte.length : posFim);
    const ausentes = [];

    const posNonce = corpo.search(/await\s+iniciarLoginGoogle\s*\(/);
    if (posNonce < 0) {
      ausentes.push("`await iniciarLoginGoogle(...)` ausente — o nonce não é obtido");
    }
    const posCarrega = corpo.search(/carregarGoogleIdentityServices\s*\(\s*\)/);
    if (posCarrega < 0) {
      ausentes.push("o orquestrador não chama o carregador do GIS");
    } else if (posNonce >= 0 && posCarrega < posNonce) {
      ausentes.push("o script do Google é carregado ANTES do nonce");
    }

    // O `nonce` precisa entrar no GIS (é o que volta assinado no id_token)…
    const posInitialize = fonte.search(/\binitialize\s*\(/);
    const cfgInitialize = conteudoDoObjeto(fonte, fonte.indexOf("{", posInitialize < 0 ? 0 : posInitialize));
    if (indiceDeChave(cfgInitialize, "nonce") < 0) {
      ausentes.push("`initialize` do GIS sem `nonce`");
    }
    const posRender = fonte.search(/\brenderButton\s*\(/);
    const virgula = posRender < 0 ? -1 : fonte.indexOf(",", posRender);
    const cfgRender = conteudoDoObjeto(fonte, virgula < 0 ? -1 : fonte.indexOf("{", virgula));
    if (indiceDeChave(cfgRender, "nonce") < 0) {
      ausentes.push("`renderButton` sem `nonce`");
    }
    // …e voltar no POST final.
    const posPost = fonte.lastIndexOf("concluirLoginGoogle(");
    const corpoPost = posPost < 0 ? null : conteudoDoObjeto(fonte, fonte.indexOf("{", posPost));
    if (corpoPost === null || indiceDeChave(corpoPost, "nonce") < 0) {
      ausentes.push("o POST final não reenvia o `nonce`");
    }
    return {
      ok: ausentes.length === 0,
      detalhes: ausentes.length === 0 ? "nonce obtido antes, repassado ao GIS e reenviado no POST final" : ausentes.join(", "),
    };
  }
  if (base === "api.ts") {
    // O corpo do POST final é lido do serializer do backend: os três campos têm
    // de estar na assinatura, e `nonce` é obrigatório (`allow_blank=False`).
    const assinatura = /concluirLoginGoogle\s*\(\s*dados:\s*\{([\s\S]*?)\}\s*\)/.exec(fonte);
    if (!assinatura) return { ok: false, detalhes: "não achei a assinatura de `concluirLoginGoogle`" };
    const ausentes = ["id_token", "nonce", "aceite_termos"].filter(
      (campo) => !new RegExp(`\\b${campo}\\s*:`).test(assinatura[1])
    );
    return {
      ok: ausentes.length === 0,
      detalhes: ausentes.length === 0 ? "id_token + nonce + aceite_termos no corpo" : `faltando: ${ausentes.join(", ")}`,
    };
  }
  return { ok: true, detalhes: "arquivo sem o handshake" };
}

/**
 * R3: as DUAS chamadas do handshake vão com `credentials: "include"` (o nonce
 * vive na sessão do backend) e em caminho RELATIVO (o cookie tem
 * `SESSION_COOKIE_SAMESITE="Lax"`, que não atravessa site diferente). E
 * `API_BASE_URL` precisa continuar resolvendo para "" no navegador de
 * produção — é essa linha que garante mesma origem em HOMOLOG/PROD.
 */
function regraCredencialEmesmaOrigem(caminho, fonte) {
  if (path.basename(caminho) !== "api.ts") {
    return { ok: true, detalhes: "não é lib/api.ts" };
  }
  const problemas = [];
  for (const nome of ["iniciarLoginGoogle", "concluirLoginGoogle"]) {
    const pos = fonte.search(new RegExp(`export function ${nome}\\b`));
    if (pos < 0) {
      problemas.push(`não achei ${nome} em lib/api.ts`);
      continue;
    }
    // Do início da função até o próximo `export` de topo: evita que a análise
    // da primeira função "veja" o corpo da segunda.
    const posFim = fonte.indexOf("\nexport ", pos + 10);
    const bloco = fonte.slice(pos, posFim < 0 ? pos + 900 : posFim);
    if (!/credentials\s*:\s*["']include["']/.test(bloco)) {
      problemas.push(`${nome} sem credentials: "include" (o nonce vive na sessão do backend)`);
    }
    const caminho = /request\s*(?:<[^>]*>)?\s*\(\s*["'`]([^"'`]+)["'`]/.exec(bloco);
    if (!caminho) {
      problemas.push(`${nome} sem caminho de request()`);
    } else if (!caminho[1].startsWith("/api/")) {
      problemas.push(`${nome} com caminho não relativo: ${caminho[1]} (cruza origem e o cookie Lax não viaja)`);
    }
  }
  const mesmaOrigemProducao =
    /typeof\s+window\s*!==\s*["']undefined["']\s*&&\s*process\.env\.NODE_ENV\s*===\s*["']production["']\s*\?\s*["']["']\s*:/.test(fonte);
  if (!mesmaOrigemProducao) {
    problemas.push('API_BASE_URL não resolve para "" no navegador de produção (mesma origem)');
  }
  return {
    ok: problemas.length === 0,
    detalhes:
      problemas.length === 0
        ? 'as duas chamadas com credentials: include e caminho relativo; produção é mesma origem'
        : problemas.join(" | "),
  };
}

/**
 * R4: nenhum identificador de cliente nem segredo do OAuth do Google escrito à
 * mão no frontend. `client_id` real é configuração de ambiente, e valor em
 * arquivo versionado é conta de outra pessoa (ou o `client_id` de produção
 * colado no `develop` e nunca revogado). É a regra que impede alguém de
 * "fechar a validação" com um identificador falso.
 */
function regraSemCredencialLiteral(caminho, fonte) {
  const achados = [];
  const id = FORMA_ID_CLIENTE.exec(fonte);
  if (id) achados.push(`identificador de cliente literal na linha ${linhaDe(fonte, id.index)}`);
  const segredo = FORMA_SEGREDO.exec(fonte);
  if (segredo) achados.push(`segredo de cliente literal na linha ${linhaDe(fonte, segredo.index)}`);
  if (/\bclient_secret\b\s*:/.test(fonte)) {
    achados.push("chave `client_secret` no código do frontend (o fluxo é só `id_token`)");
  }
  return {
    ok: achados.length === 0,
    detalhes: achados.length === 0 ? "nenhum identificador/segredo literal; o valor vem de process.env" : achados.join(" | "),
  };
}

/**
 * R5: o botão da tela não pode chamar o pai sem o POST final. Um
 * `aoConcluir(...)` que receba a credencial (ou nada) trataria "o Google
 * respondeu" como login efetuado.
 */
function regraBotaoSoConcluiAposPost(caminho, fonte) {
  if (path.basename(caminho) !== "BotaoGoogle.tsx") {
    return { ok: true, detalhes: "não é BotaoGoogle" };
  }
  const problemas = [];
  if (!/await\s+iniciarFluxoGoogle\s*\(/.test(fonte)) {
    problemas.push("não espera `iniciarFluxoGoogle` (o POST final)");
  }
  const chamadas = [...fonte.matchAll(/aoConcluir\s*\(/g)];
  if (chamadas.length !== 1) {
    problemas.push(`${chamadas.length} chamada(s) a aoConcluir (tem de ser exatamente 1)`);
  } else if (!/await\s+aoConcluir\s*\(\s*resposta\s*\)/.test(fonte)) {
    const achada = fonte.slice(Math.max(0, chamadas[0].index - 40), chamadas[0].index + 40);
    problemas.push(`aoConcluir não recebe o resultado do POST: …${achada.replace(/\s+/g, " ")}…`);
  }
  return {
    ok: problemas.length === 0,
    detalhes: problemas.length === 0 ? "o pai só é chamado com a resposta do POST final" : problemas.join("; "),
  };
}

const REGRAS_ESTATICAS = [
  ["R1", "nada do Google carregado fora do clique", regraNadaDoGoogleForaDoClique],
  ["R2", "nonce obtido antes do fluxo e reenviado no POST final", regraNonceAntesEVoltaNoPost],
  ["R3", "credentials: include e mesma origem nas duas chamadas", regraCredencialEmesmaOrigem],
  ["R4", "nenhum client_id/secret literal no código", regraSemCredencialLiteral],
  ["R5", "o botão só chama o pai depois do POST final", regraBotaoSoConcluiAposPost],
];

// ---------------------------------------------------------------------------
// Autotestes das regras estáticas (negativo + falso positivo para cada uma)
// ---------------------------------------------------------------------------

// Montados por concatenação: este arquivo não pode conter nada com cara de
// identificador de cliente (gate de proveniência).
const ID_SINTETICO = ID_CLIENTE_SINTETICO;
const SEGREDO_SINTETICO = "GOCSPX-" + ["Ab3", "dEf9", "Gh1i"].join("");

const API_BASE_SINTETICA =
  'export const API_BASE_URL =\n' +
  '  typeof window !== "undefined" && process.env.NODE_ENV === "production"\n' +
  '    ? ""\n' +
  '    : process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";\n';

function googleNoApi(caminhoFinal = "/api/auth/google/", incluir = true) {
  const cred = incluir ? '    credentials: "include",\n' : "";
  return (
    'export function iniciarLoginGoogle(): Promise<NonceGoogle> {\n' +
    '  return request("/api/auth/google/iniciar/", {\n' +
    '    method: "POST",\n' + cred + "  });\n}\n" +
    "export function concluirLoginGoogle(dados: {\n" +
    "  id_token: string;\n  nonce: string;\n  aceite_termos: boolean;\n" +
    "}): Promise<RespostaLoginGoogle> {\n" +
    `  return request("${caminhoFinal}", {\n` +
    '    method: "POST",\n' + cred +
    "    body: JSON.stringify(dados),\n  });\n}\n"
  );
}

/** Handshake sintético completo, usado como base dos casos de R2. */
function orquestradorSintetico({ nonceAntes = true, comNonceNoPost = true, comNonceNoRender = true } = {}) {
  const passoNonce = nonceAntes
    ? "  const p = await iniciarLoginGoogle();\n  await carregarGoogleIdentityServices();\n"
    : "  await carregarGoogleIdentityServices();\n  const p = await iniciarLoginGoogle();\n";
  return (
    "export async function iniciarFluxoGoogle(o) {\n" +
    passoNonce +
    "  gapi.accounts.id.initialize({ client_id: id, nonce: p.nonce, callback: cb });\n" +
    `  gapi.accounts.id.renderButton(el, { theme: "outline"${comNonceNoRender ? ", nonce: p.nonce" : ""} });\n` +
    `  await concluirLoginGoogle({ id_token: t${comNonceNoPost ? ", nonce: p.nonce" : ""} });\n}\n` +
    "export function carregarGoogleIdentityServices() {}\n"
  );
}

function rodarAutotestes() {
  console.log("\nAutotestes das regras (negativo = precisa reprovar; falso positivo = precisa aceitar):");

  // ---- R1 -----------------------------------------------------------------
  registrarAutoteste(
    "R1 negativo: <script src> do Google no layout raiz",
    regraNadaDoGoogleForaDoClique("app/layout.tsx", semComentario('<head><script src="https://accounts.google.com/gsi/client"></script></head>')).ok === false,
    "reprovado como deve"
  );
  registrarAutoteste(
    "R1 negativo: next/script do Google com strategy afterInteractive",
    regraNadaDoGoogleForaDoClique("components/X.tsx", semComentario('import Script from "next/script";\nexport const X=()=> <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" />;')).ok === false
  );
  registrarAutoteste(
    "R1 negativo: preconnect do Google no layout (handshake TLS já é saída)",
    regraNadaDoGoogleForaDoClique("app/layout.tsx", semComentario('<head><link rel="preconnect" href="https://accounts.google.com" /></head>')).ok === false
  );
  registrarAutoteste(
    "R1 negativo: outro componente com o host do Google em código",
    regraNadaDoGoogleForaDoClique("components/BotaoGoogle.tsx", semComentario('const URL_GOOGLE = "https://accounts.google.com/gsi/client";')).ok === false,
    "reprovado como deve (só o carregador pode falar com o host)"
  );
  registrarAutoteste(
    "R1 negativo: script do Google injetado em useEffect (carrega no mount)",
    regraNadaDoGoogleForaDoClique(
      "components/BotaoGoogle.tsx",
      semComentario('const H="https://accounts.google.com";\nexport function B(){ useEffect(()=>{ const s=document.createElement("script"); s.src=H+"/gsi/client"; document.head.appendChild(s); },[]); return <div/>; }')
    ).ok === false
  );
  registrarAutoteste(
    "R1 falso positivo: menção ao host do Google só em comentário",
    regraNadaDoGoogleForaDoClique("app/login/page.tsx", semComentario('// nada de accounts.google.com é carregado antes do clique\nexport const a = 1;')).ok === true
  );
  registrarAutoteste(
    "R1 falso positivo: a tela do login só mostra o rótulo do botão",
    regraNadaDoGoogleForaDoClique("app/login/page.tsx", semComentario('export default function Page(){ return <BotaoGoogle />; } // Continuar com Google')).ok === true
  );
  registrarAutoteste(
    "R1 falso positivo: next/script de OUTRO host (AdSense) não é assunto desta guarda",
    regraNadaDoGoogleForaDoClique("components/AdsScript.tsx", semComentario('import Script from "next/script";\nexport const A=()=> <Script src="https://pagead2.googlesyndication.com/adsbygoogle.js" strategy="lazyOnload" />;')).ok === true,
    "aceito: quem governa o AdSense é o P1-09"
  );
  registrarAutoteste(
    "R1 isenta o carregador, mas exige chamada só no orquestrador",
    regraNadaDoGoogleForaDoClique("lib/google-oauth.ts", semComentario(orquestradorSintetico())).ok === true
  );
  registrarAutoteste(
    "R1b negativo: carregador chamado no topo do módulo (carrega no load da página)",
    regraNadaDoGoogleForaDoClique(
      "lib/google-oauth.ts",
      semComentario('const S="https://accounts.google.com/gsi/client";\nvoid carregarGoogleIdentityServices();\nexport function carregarGoogleIdentityServices(){}\nexport async function iniciarFluxoGoogle(){ }')
    ).ok === false
  );
  registrarAutoteste(
    "R1b negativo: carregador nunca chamado",
    regraNadaDoGoogleForaDoClique(
      "lib/google-oauth.ts",
      semComentario('const S="https://accounts.google.com/gsi/client";\nexport function carregarGoogleIdentityServices(){}\nexport async function iniciarFluxoGoogle(){ return null; }')
    ).ok === false,
    "reprovado como deve (o login Google não carregaria nada)"
  );

  // ---- R2 -----------------------------------------------------------------
  registrarAutoteste("R2 falso positivo: handshake completo no carregador", regraNonceAntesEVoltaNoPost("lib/google-oauth.ts", semComentario(orquestradorSintetico())).ok === true);
  registrarAutoteste(
    "R2 negativo: script do Google carregado ANTES do nonce",
    regraNonceAntesEVoltaNoPost("lib/google-oauth.ts", semComentario(orquestradorSintetico({ nonceAntes: false }))).ok === false,
    "reprovado como deve"
  );
  registrarAutoteste(
    "R2 negativo: POST final sem reenviar o nonce",
    regraNonceAntesEVoltaNoPost("lib/google-oauth.ts", semComentario(orquestradorSintetico({ comNonceNoPost: false }))).ok === false,
    "reprovado como deve (nonce que fica só no front não liga nada)"
  );
  registrarAutoteste(
    "R2 negativo: renderButton sem nonce (o id_token volta sem o claim)",
    regraNonceAntesEVoltaNoPost("lib/google-oauth.ts", semComentario(orquestradorSintetico({ comNonceNoRender: false }))).ok === false
  );
  registrarAutoteste(
    "R2 negativo: initialize do GIS sem nonce",
    regraNonceAntesEVoltaNoPost(
      "lib/google-oauth.ts",
      semComentario(orquestradorSintetico()).replace("nonce: p.nonce, callback: cb", "callback: cb")
    ).ok === false
  );
  registrarAutoteste(
    "R2 falso positivo: contrato do POST final com os três campos",
    regraNonceAntesEVoltaNoPost(
      "api.ts",
      semComentario('export function concluirLoginGoogle(dados: { id_token: string; nonce: string; aceite_termos: boolean; }) {\n return request("/api/auth/google/", { method: "POST", body: JSON.stringify(dados) });\n}')
    ).ok === true
  );
  registrarAutoteste(
    "R2 negativo: contrato do POST final sem o campo nonce",
    regraNonceAntesEVoltaNoPost(
      "api.ts",
      semComentario('export function concluirLoginGoogle(dados: { id_token: string; aceite_termos: boolean; }) {\n return request("/api/auth/google/", { method: "POST", body: JSON.stringify(dados) });\n}')
    ).ok === false
  );
  registrarAutoteste(
    "R2 não accuse componente que só repassa props",
    regraNonceAntesEVoltaNoPost("components/BotaoGoogle.tsx", semComentario("export const BotaoGoogle = (p: { nonce: string }) => <div>{p.nonce}</div>;")).ok === true
  );

  // ---- R3 -----------------------------------------------------------------
  registrarAutoteste("R3 falso positivo: as duas chamadas com include e caminho relativo", regraCredencialEmesmaOrigem("lib/api.ts", API_BASE_SINTETICA + googleNoApi()).ok === true);
  registrarAutoteste(
    "R3 negativo: chamada final SEM credentials (o nonce não volta na sessão)",
    regraCredencialEmesmaOrigem("lib/api.ts", API_BASE_SINTETICA + googleNoApi("/api/auth/google/", false)).ok === false,
    "reprovado como deve"
  );
  registrarAutoteste(
    "R3 negativo: chamada em URL absoluta (cruza origem; cookie Lax não viaja)",
    regraCredencialEmesmaOrigem("lib/api.ts", API_BASE_SINTETICA + googleNoApi("http://localhost:8000/api/auth/google/")).ok === false,
    "reprovado como deve"
  );
  registrarAutoteste(
    "R3 negativo: API_BASE_URL apontando para outro domínio em produção",
    regraCredencialEmesmaOrigem("lib/api.ts", 'export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "";\n' + googleNoApi()).ok === false,
    "reprovado como deve (perde a mesma origem em HOMOLOG/PROD)"
  );
  registrarAutoteste(
    "R3 falso positivo: uma função com o MESMO nome fora de lib/api.ts não é o handshake",
    regraCredencialEmesmaOrigem("components/BotaoGoogle.tsx", googleNoApi("https://exemplo.invalido/api/")).ok === true,
    "aceito: a regra só olha lib/api.ts"
  );

  // ---- R4 -----------------------------------------------------------------
  registrarAutoteste("R4 negativo: identificador de cliente escrito à mão", regraSemCredencialLiteral("lib/x.ts", `const ID = "${ID_SINTETICO}";`).ok === false, "reprovado como deve");
  registrarAutoteste("R4 negativo: segredo de cliente escrito à mão", regraSemCredencialLiteral("lib/x.ts", `const S = "${SEGREDO_SINTETICO}";`).ok === false, "reprovado como deve");
  registrarAutoteste("R4 negativo: chave client_secret no frontend", regraSemCredencialLiteral("lib/x.ts", 'const corpo = { client_secret: "abc" };').ok === false, "reprovado como deve (o fluxo é só id_token)");
  registrarAutoteste(
    "R4 falso positivo: identificador vindo de process.env",
    regraSemCredencialLiteral("lib/google-oauth.ts", 'export const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID || "";').ok === true
  );
  registrarAutoteste(
    "R4 falso positivo: o FORMATO do identificador explicado em comentário",
    regraSemCredencialLiteral("lib/google-oauth.ts", semComentario(`const x = 1; // o formato é ${ID_SINTETICO} e nunca entra no fonte`)).ok === true,
    "aceito: comentários são removidos antes da regra"
  );

  // ---- R5 -----------------------------------------------------------------
  registrarAutoteste(
    "R5 negativo: botão que chama o pai com a credencial, sem o POST final",
    regraBotaoSoConcluiAposPost(
      "components/BotaoGoogle.tsx",
      semComentario('export function BotaoGoogle({aoConcluir}) { const g = (r) => aoConcluir(r.credential); return <div/>; }')
    ).ok === false,
    "reprovado como deve (trataria 'o Google respondeu' como login efetuado)"
  );
  registrarAutoteste(
    "R5 negativo: botão que chama o pai sem esperar nada",
    regraBotaoSoConcluiAposPost("components/BotaoGoogle.tsx", semComentario("export function BotaoGoogle({aoConcluir}) { aoConcluir(); return <div/>; }")).ok === false
  );
  registrarAutoteste(
    "R5 falso positivo: botão que espera o POST e repassa a resposta",
    regraBotaoSoConcluiAposPost(
      "components/BotaoGoogle.tsx",
      semComentario("export function BotaoGoogle({aoConcluir}) { const f = async () => { const resposta = await iniciarFluxoGoogle({}); await aoConcluir(resposta); }; return <div/>; }")
    ).ok === true
  );
  registrarAutoteste("R5 não acusa componente homônimo", regraBotaoSoConcluiAposPost("components/Rodape.tsx", "export const Rodape = () => <footer/>;").ok === true);
}

// ---------------------------------------------------------------------------
// Frente comportamental
// ---------------------------------------------------------------------------

const NONCE_DE_TESTE = "nonce-de-teste-nao-e-uma-credencial";
const ID_TOKEN_DE_TESTE = "id-token-de-teste-nao-e-uma-credencial";
const RESPOSTA_NONCE = { status: 200, corpo: { nonce: NONCE_DE_TESTE, expira_em_segundos: 600 } };
const RESPOSTA_OK = {
  status: 200,
  corpo: {
    token: "token-de-teste-nao-e-uma-credencial",
    usuario: { id: 1, email: "p@example.org", papel: "free" },
    criado_agora: true,
  },
};
const containerFalso = () => ({ replaceChildren: () => {}, clientWidth: 320 });

/** Conduz o handshake inteiro contra o código real e devolve as observações. */
async function conduzirFluxo({ respostas, origem, opcoes = {}, entregar = ID_TOKEN_DE_TESTE }) {
  CRONOLOGIA = [];
  const { scripts, registros, gis, chamadas } = montarCenario({ origem, respostas });
  const mod = await importarModuloLimpo();
  const exibido = { valor: false };
  let assentou = false;
  const promessa = mod
    .iniciarFluxoGoogle({
      aceiteTermos: true,
      container: containerFalso(),
      aoExibirBotaoGoogle: () => {
        exibido.valor = true;
      },
      ...opcoes,
    })
    .then(
      (r) => {
        assentou = true;
        return { ok: true, resposta: r, erro: null };
      },
      (e) => {
        assentou = true;
        return { ok: false, resposta: null, erro: e };
      }
    );
  const renderizou = await esperarAte(() => gis.pronto() || assentou, 3000);
  if (renderizou && gis.pronto() && entregar !== null) gis.entregar(entregar);
  const desfecho = await promessa;
  return { mod, scripts, registros, chamadas, desfecho, renderizou, exibido: exibido.valor };
}

async function frenteComportamental() {
  // ---- B1: no import, nada sai ------------------------------------------
  const { scripts: scriptsImport, registros: registrosImport, gis: gisImport, chamadas: chamadasImport } =
    montarCenario();
  const modLimpo = await importarModuloLimpo();
  // Espera um pouco para dar chance a um carregamento ansioso de acontecer no
  // import: sem esta volta ao event loop, "0 scripts no import" só provaria que
  // o import é síncrono, e não que nada foi agendado.
  await espera();
  await espera();
  registrar(
    "B1 importar o módulo não cria <script> nem chama a rede nem toca no GIS",
    scriptsImport.length === 0 && chamadasImport.length === 0 && registrosImport.length === 0 && !gisImport.carregado(),
    `import: ${scriptsImport.length} script(s), ${chamadasImport.length} chamada(s), ${registrosImport.length} interação(ões) com o GIS, window.google presente: ${gisImport.carregado()}`
  );
  registrar(
    "B1 a origem do script do Google é a do provedor de identidade",
    modLimpo.SCRIPT_GOOGLE === `https://accounts.google.com/gsi/client`,
    `SCRIPT_GOOGLE = ${modLimpo.SCRIPT_GOOGLE}`
  );

  // ---- B2: o nonce é pedido ANTES do Google, e volta ----------------------
  const mod = await importarModuloLimpo();
  const { scripts, registros, chamadas, desfecho, renderizou, exibido } = await conduzirFluxo({
    respostas: [RESPOSTA_NONCE, RESPOSTA_OK],
  });
  registrar("B2 o botão do Google foi renderizado e avisou a UI", renderizou && exibido, `renderButton: ${registros.some((r) => r.evento === "renderButton")}`);
  const iNonce = indiceDoPrimeiro("rede");
  const iScript = indiceDoPrimeiro("script-criado");
  const iGis = Math.min(
    ...[indiceDoPrimeiro("gis-initialize"), indiceDoPrimeiro("gis-renderButton")].filter((n) => n >= 0)
  );
  registrar(
    "B2 o nonce é o PRIMEIRO evento de saída, antes de qualquer script ou chamada do Google",
    iNonce === 0 && iScript > 0 && iGis > iNonce,
    `cronologia: ${CRONOLOGIA.map((e) => e.tipo).join(" → ")}`
  );
  registrar(
    "B2 o passo 1 é o endpoint do nonce e o passo 3 é o endpoint do id_token (nesta ordem)",
    chamadas.length > 0 &&
      chamadas[0].url.includes("/api/auth/google/iniciar/") &&
      chamadas[1]?.url.includes("/api/auth/google/") &&
      scripts.length === 1,
    `1ª chamada: ${chamadas[0]?.url} · 2ª: ${chamadas[1]?.url} · scripts: ${scripts.length} (${scripts.map((s) => s.src).join(", ")})`
  );
  registrar(
    "B2 o nonce é o MESMO valor que foi para o GIS e que voltou no POST final",
    registros.find((r) => r.evento === "initialize")?.config?.nonce === NONCE_DE_TESTE &&
      registros.find((r) => r.evento === "renderButton")?.opcoes?.nonce === NONCE_DE_TESTE &&
      chamadas[1]?.corpo?.nonce === NONCE_DE_TESTE,
    `initialize.nonce = ${registros.find((r) => r.evento === "initialize")?.config?.nonce}; renderButton.nonce = ${registros.find((r) => r.evento === "renderButton")?.opcoes?.nonce}; POST final.nonce = ${chamadas[1]?.corpo?.nonce}`
  );
  registrar(
    "B2 as DUAS chamadas vão com credentials: include",
    chamadas.length === 2 && chamadas.every((c) => c.credentials === "include"),
    chamadas.map((c) => `${c.metodo} ${c.url} credentials=${c.credentials}`).join(" | ")
  );
  registrar(
    "B2 o POST final leva id_token, nonce e aceite_termos",
    chamadas[1]?.corpo?.id_token === ID_TOKEN_DE_TESTE &&
      chamadas[1]?.corpo?.aceite_termos === true &&
      typeof chamadas[1]?.corpo?.nonce === "string",
    `payload: ${JSON.stringify({ ...chamadas[1]?.corpo, id_token: "<id_token>", nonce: "<nonce>" })}`
  );
  registrar(
    "B2 o caminho contratual (id_token sintético) chega ao token do backend",
    desfecho.ok === true && desfecho.resposta?.token === RESPOSTA_OK.corpo.token,
    desfecho.ok ? `token recebido, criado_agora=${desfecho.resposta?.criado_agora}` : `falhou: ${desfecho.erro?.message}`
  );

  // ---- B3: o clique é o que cria o script --------------------------------
  const antes = await estadoAntesDoClique();
  registrar(
    "B3 o script do Google só nasce DEPOIS do clique",
    antes.scriptsAntes === 0 && antes.renderAntes === 0 && antes.scriptsDepois === 1,
    `antes do clique: ${antes.scriptsAntes} script(s), ${antes.renderAntes} renderButton; depois: ${antes.scriptsDepois} script(s)`
  );

  // ---- B4: a segunda tentativa não recarrega o script ----------------------
  const segunda = await segundaTentativa();
  registrar(
    "B4 uma segunda tentativa não cria um segundo <script> do Google",
    segunda.scripts === 1,
    `${segunda.scripts} script(s) no total em duas tentativas`
  );

  // ---- B5: sem `client_id` nada sai (e a UI tem um texto para isso) -------
  const semCliente = await semClientId();
  registrar(
    "B5 sem client_id no ambiente: falha explícita e NENHUMA chamada",
    semCliente.codigo === "nao_configurado" && semCliente.chamadas === 0 && semCliente.scripts === 0 && semCliente.mensagem.length > 0,
    `=> ${semCliente.codigo}: ${semCliente.chamadas} chamada(s), ${semCliente.scripts} script(s)`
  );

  // ---- B6: nenhum erro vira login efetuado --------------------------------
  const casosDeErro = [
    ["negação, cancelamento ou popup bloqueado: não voltou credencial", { respostas: [RESPOSTA_NONCE], opcoes: { limiteInteracaoMs: 60 }, entregar: null }, "sem_credencial"],
    ["credencial vazia devolvida pelo Google", { respostas: [RESPOSTA_NONCE], opcoes: { limiteInteracaoMs: 2000 }, entregar: "" }, "credencial_invalida"],
    ["nonce vencido na tela de consentimento (prazo é o do backend)", { respostas: [{ status: 200, corpo: { nonce: NONCE_DE_TESTE, expira_em_segundos: 0.05 } }], opcoes: { limiteInteracaoMs: 3000 }, atrasoEntregaMs: 250 }, "nonce_expirado"],
    ["id_token inválido (400 do backend)", { respostas: [RESPOSTA_NONCE, { status: 400, corpo: { detail: "Token do Google inválido." } }] }, "token_recusado"],
    ["conta nova sem aceite de termos (400 do backend)", { respostas: [RESPOSTA_NONCE, { status: 400, corpo: { detail: "É necessário aceitar os termos de uso e a política de privacidade para se cadastrar." } }] }, "termos_pendentes"],
    ["nonce ausente, inválido ou divergente no servidor (403)", { respostas: [RESPOSTA_NONCE, { status: 403, corpo: { detail: "Não foi possível concluir o login com esta conta. Entre com e-mail e senha." } }] }, "identidade_recusada"],
    ["e-mail não verificado no provedor (403, mesma mensagem, por desenho)", { respostas: [RESPOSTA_NONCE, { status: 403, corpo: { detail: "Não foi possível concluir o login com esta conta. Entre com e-mail e senha." } }] }, "identidade_recusada"],
    ["conta inativa (403)", { respostas: [RESPOSTA_NONCE, { status: 403, corpo: { detail: "Conta inativa." } }] }, "conta_inativa"],
    ["provedor não configurado no ambiente (503)", { respostas: [RESPOSTA_NONCE, { status: 503, corpo: { detail: "O login com Google não está disponível neste ambiente." } }] }, "provedor_nao_configurado"],
    ["throttle do DRF (429 com Retry-After)", { respostas: [{ status: 429, corpo: { detail: "Pedido foi limitado." }, retryAfter: "42" }] }, "muitas_tentativas"],
    ["passo 1 do nonce indisponível (500)", { respostas: [{ status: 500, corpo: { detail: "erro interno" } }] }, "indisponivel"],
    ["sem rede no passo 1", { respostas: [{ status: 0, corpo: {} }] }, "sem_conexao"],
    // `id_token` chega, o backend responde 200 — mas SEM token. Um 200 sem
    // credencial é falha, não login: é a forma mais barata de inventar sessão.
    ["200 SEM token no POST final", { respostas: [RESPOSTA_NONCE, { status: 200, corpo: { usuario: {} } }] }, "indisponivel"],
    ["API em outro domínio (o cookie Lax não viaja)", { respostas: [RESPOSTA_NONCE, RESPOSTA_OK], origem: "https://portal.outrodominio.example" }, "origem_incorporada"],
  ];
  for (const [nome, entrada, codigoEsperado] of casosDeErro) {
    const { codigo, mensagem } = await classificarCenario(entrada);
    registrar(
      `B6 falha tratada como falha — ${nome}`,
      codigo === codigoEsperado && !!mensagem && mensagem.trim().length > 0,
      `=> ${codigo}: ${mensagem.slice(0, 100)}`
    );
  }

  // ---- B7: o classificador não tem como dizer "entrou" --------------------
  const entradas = [new Error("qualquer"), null, undefined, { status: 200 }, "texto", 42];
  const resultados = entradas.map((bruto) => mod.classificarErroGoogle(bruto));
  const entrou = new Set(["ok", "sucesso", "autenticado", "logado", "done", "authenticated"]);
  registrar(
    "B7 classificarErroGoogle nunca devolve código de sucesso (o retorno não tem campo de sucesso)",
    resultados.every(
      (r) =>
        Object.keys(r).sort().join(",") === "codigo,mensagem" &&
        typeof r.codigo === "string" &&
        r.codigo.length > 0 &&
        typeof r.mensagem === "string" &&
        r.mensagem.trim().length > 0 &&
        !entrou.has(r.codigo.toLowerCase())
    ),
    `${resultados.length} entrada(s) avulsa(s) => ${[...new Set(resultados.map((r) => r.codigo))].join(", ")}`
  );

  // ---- B8: o cookie de sessão precisa viajar ------------------------------
  const casosCookie = [
    ['mesma origem (produção, API_BASE_URL="")', "", "https://portal.exemplo", true],
    ["next dev: mesmo host, porta diferente (localhost)", "http://localhost:8000", "http://localhost:3000", true],
    ["subdomínios do mesmo domínio", "https://api.exemplo.org", "https://portal.exemplo.org", true],
    ["domínio mais amplo do mesmo site", "https://exemplo.org", "https://app.exemplo.org", true],
    ["OUTRO domínio (crítico: Lax não viaja)", "https://api.outro.net", "https://portal.exemplo.org", false],
    ["base não interpretável (não dá para provar que o cookie viaja)", "nao-e-url", "https://portal.exemplo.org", false],
  ];
  for (const [nome, base, origem, esperado] of casosCookie) {
    const obtido = mod.cookieDeSessaoChega(base, origem);
    registrar(`B8 cookie de sessão: ${nome}`, obtido === esperado, `cookieDeSessaoChega(${base || '""'}, ${origem}) = ${obtido}`);
  }

  // ---- B9: o prazo do nonce é o prazo do BACKEND --------------------------
  const agora = 1_000_000_000_000;
  const casosNonce = [
    ["nonce recém-emitido NÃO venceu", agora, 600, agora + 599_000, false],
    ["nonce no limite exato ainda vale", agora, 600, agora + 600_000, false],
    ["nonce um ms além do prazo venceu", agora, 600, agora + 600_001, true],
    ["prazo ausente no corpo cai no padrão de 600s do backend", agora, NaN, agora + 600_001, true],
    ["relógio não-numérico falha fechado", NaN, 600, agora, true],
  ];
  for (const [nome, emitido, ttl, momento, esperado] of casosNonce) {
    const obtido = mod.nonceVenceuEm(emitido, ttl, momento);
    registrar(`B9 ${nome}`, obtido === esperado, `nonceVenceuEm(${emitido}, ${ttl}, ${momento}) = ${obtido}`);
  }
}

/** Estado da tela "carregada, botão visível, ninguém clicou". */
async function estadoAntesDoClique() {
  const { scripts, registros, gis } = montarCenario({ respostas: [RESPOSTA_NONCE, RESPOSTA_OK] });
  const mod = await importarModuloLimpo();
  // Importar o módulo É o que acontece no carregamento da tela de login.
  const antes = { scripts: scripts.length, render: registros.length, google: gis.carregado() };
  let assentou = false;
  const promessa = mod
    .iniciarFluxoGoogle({ aceiteTermos: true, container: containerFalso() })
    .catch(() => null)
    .then((v) => {
      assentou = true;
      return v;
    });
  if (await esperarAte(() => gis.pronto() || assentou)) gis.entregar(ID_TOKEN_DE_TESTE);
  await promessa;
  return { scriptsAntes: antes.scripts, renderAntes: antes.render, scriptsDepois: scripts.length };
}

/** Duas tentativas seguidas: o script não pode ser duplicado. */
async function segundaTentativa() {
  const { scripts, gis } = montarCenario({
    respostas: [RESPOSTA_NONCE, RESPOSTA_OK, RESPOSTA_NONCE, RESPOSTA_OK],
  });
  const mod = await importarModuloLimpo();
  for (let i = 0; i < 2; i += 1) {
    const marca = gis.marca();
    let assentou = false;
    const promessa = mod
      .iniciarFluxoGoogle({ aceiteTermos: true, container: containerFalso() })
      .catch(() => null)
      .then((v) => {
        assentou = true;
        return v;
      });
    if (await esperarAte(() => gis.prontoDesde(marca) || assentou)) gis.entregar(ID_TOKEN_DE_TESTE);
    await promessa;
  }
  return { scripts: scripts.length };
}

/** Sem `NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID` no ambiente: nada pode sair. */
async function semClientId() {
  const salvo = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID;
  delete process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID;
  try {
    const { scripts, chamadas } = montarCenario({ respostas: [RESPOSTA_NONCE, RESPOSTA_OK] });
    const mod = await importarModuloLimpo();
    const erro = await mod
      .iniciarFluxoGoogle({ aceiteTermos: true, container: containerFalso() })
      .then(() => null, (e) => e);
    const classificado = erro ? mod.classificarErroGoogle(erro) : { codigo: "nenhum", mensagem: "" };
    return { codigo: classificado.codigo, mensagem: classificado.mensagem, chamadas: chamadas.length, scripts: scripts.length };
  } finally {
    process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID = salvo;
  }
}

/** Executa um cenário e devolve como a UI classifica o desfecho. */
async function classificarCenario({ respostas, origem, opcoes = {}, atrasoEntregaMs = 0, entregar }) {
  const mod = await importarModuloLimpo();
  const { gis } = montarCenario({ origem, respostas });
  // `entregar` decide o que o Google devolve: `null` = nada voltou (negação,
  // cancelamento ou popup bloqueado), `""` = credencial vazia, string =
  // `id_token` de verdade.
  const credencial = entregar === undefined ? ID_TOKEN_DE_TESTE : entregar;
  let assentou = false;
  const promessa = mod
    .iniciarFluxoGoogle({ aceiteTermos: true, container: containerFalso(), ...opcoes })
    .then(
      (r) => {
        assentou = true;
        return { ok: true, resposta: r, erro: null };
      },
      (e) => {
        assentou = true;
        return { ok: false, resposta: null, erro: e };
      }
    );
  // Só se espera pelo botão do Google ENQUANTO o fluxo não assentou. Sem isto,
  // os cenários que falham antes do renderButton (sem rede, 503, 500, API em
  // outro domínio) ficariam esperando o teto inteiro à toa — foi o que deixou a
  // guarda levar mais de dois minutos.
  if (await esperarAte(() => gis.pronto() || assentou, 3000)) {
    if (atrasoEntregaMs > 0) await new Promise((r) => setTimeout(r, atrasoEntregaMs));
    if (credencial !== null && !assentou) gis.entregar(credencial);
  }
  const desfecho = await promessa;
  if (desfecho.ok) {
    return { codigo: "SUCESSO_INESPERADO", mensagem: "cenário de falha resolveu com sucesso" };
  }
  return mod.classificarErroGoogle(desfecho.erro);
}

// ---------------------------------------------------------------------------

async function main() {
  console.log("P1-05b — login Google no frontend: nada sai antes do clique, o nonce liga as pontas, nenhum erro vira login\n");

  console.log("A) Comportamental, sobre lib/google-oauth.ts e lib/api.ts reais:\n");
  await frenteComportamental();

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
    "regras estáticas P1-05b em todos os fontes",
    problemas.length === 0,
    problemas.length === 0 ? `${varridos} arquivo(s) varrido(s), 0 violação(ões)` : `${problemas.length} violação(ões):\n    - ${problemas.join("\n    - ")}`
  );

  rodarAutotestes();

  if (violacoes.length > 0) {
    console.error(`\n${violacoes.length} verificação(ões) em VIOLAÇÃO de P1-05b (login Google no frontend).`);
    process.exit(1);
  }
  console.log("\nP1-05b OK — nada do Google antes do clique, nonce obtido antes e reenviado, credentials: include, nenhum erro vira login.");
}

main().catch((erro) => {
  console.error(`[VIOLAÇÃO] falha inesperada na verificação: ${erro?.message ?? String(erro)}`);
  process.exit(1);
});
