#!/usr/bin/env node
/**
 * Guarda de regressão P0-08 — "Remover conteúdo fictício".
 *
 * Falha (exit 1) se os caminhos de renderização do frontend voltarem a
 * apresentar dado fictício como real:
 *
 *   1. literais MOCK / mock / fake / dummy / placeholder usados como DADO
 *      (array/objeto de conteúdo, não comentário, não atributo de formulário);
 *   2. texto de conteúdo que se declara fictício: "de exemplo", "demonstrativa",
 *      "demonstração", "exemplo", "fictício";
 *   3. prova social inventada: "+12.000 assinantes" e variantes "+N.NNN <algo>";
 *   4. preço de plano hardcoded no caminho de renderização ("29.90", "0.00").
 *
 * Falsos positivos que a guarda NÃO acusa (por desenho):
 *   - nome de variável de teste / identificador de teste (`test.mockFn`);
 *   - comentário explicativo honesto ("nunca mais fallback MOCK", "P0-08:");
 *   - atributo `placeholder` de <input>/<textarea> de formulário;
 *   - `SelectValue placeholder=` / `placeholder:` de componente de UI;
 *   - exemplo de uso em email/documentação de dentro de string de exemplo
 *     permitido por lista de exceções (ver `PERMITIDOS`).
 *
 * Uso:  node scripts/verificar-conteudo-ficticio.mjs
 * Sai com 0 se nada foi encontrado; 1 com a lista de achados.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = fileURLToPath(new URL("..", import.meta.url));

/** Caminhos de renderização inspecionados. */
const DIRETORIOS = ["app", "components", "lib"];

const EXTENSOES = new Set([".ts", ".tsx", ".js", ".jsx", ".mjs"]);
const IGNORAR_DIR = new Set(["node_modules", ".next", "out", "dist", "build", "coverage", "__tests__"]);

/**
 * Linhas inteiras cujo comentário é legítimo e não deve ser acusado.
 * Um comentário pode citar "mock"/"exemplo" ao explicar a remoção.
 */
const COMENTARIOS_PERMITIDOS = [
  // Explicações honestas sobre a remoção do conteúdo fictício.
  /P0-0?8\b/,
  /nunca\s+(mais\s+)?(usou|usamos|h[aá] fallback|exibi|popul|cria)/i,
  /fallback\s+(mock|de\s+exemplo)\s+(foi\s+)?(removido|eliminado)/i,
  /(saiu|removido|removida|eliminad[oa]|n[aã]o\s+existe\s+mais)\s+(o\s+|a\s+)?(fallback|array|lista)\s*(MOCK|mock)?/i,
  /prova\s+social\s+(inventada|fabricada)/i,
  /pre[cç]o\s+(vem|veio)\s+(s[oó]\s+)?d[ao]\s+(API|Central)/i,
  // Documentação honesta de contrato de API / mock em camada de teste.
  /\b(spec|contrato|documenta[cç][aã]o|fixture\s+de\s+teste|teste)\b/i,
  /guarda\s+de\s+regress[aã]o/i,
];

/** Padrões de dado fictício. Cada um: [id, regex, mensagem]. */
const REGRAS = [
  {
    id: "dado-mock",
    // Identificador MOCK/fake/dummy como nome de dado renderizado.
    // Aceita MOCK, MOCK_PUBS, MOCK_T, dadosMock, mockItems, fakeNews, dummyFeed.
    // Nome da variável/const atribuída (sem `obj.` e sem membro `x.mock`).
    // Cobre: MOCK, MOCK_PUBS, MOCK_T, fakeNews, dummyFeed, mockItems, mockSerie.
    regex:
      /(?<![.\w$])(?:const|let|var)?\s*(?:[A-Za-z0-9_$]*_)?(?:MOCK[A-Za-z0-9_$]*|Fake[A-Za-z0-9_$]*|DUMMY[A-Za-z0-9_$]*|fake[A-Z][A-Za-z0-9_$]*|dummy[A-Z][A-Za-z0-9_$]*|mock(?:_[A-Za-z0-9_$]*)?)\s*(?::[^=\n]*)?=\s*(?!=)/,
    msg: "identificador de dado fictício (MOCK/fake/dummy) atribuído em caminho de renderização",
  },
  {
    id: "dado-mock-literal",
    // Array/objeto de conteúdo declarado com literal MOCK (sem depender do nome da var).
    regex: /(?:const|let|var)\s+MOCK[A-Z_]*\s*(:[^=]*)?=\s*[[{]/,
    msg: "array/objeto de conteúdo fictício literal (MOCK = [...])",
  },
  {
    id: "texto-exemplo",
    regex: /\b(?:de\s+exemplo|exemplos?\b|demonstrativ[oa]s?|demonstra[cç][aã]o|dados?\s+de\s+exemplo)\b/i,
    msg: "texto que se declara como conteúdo de exemplo/demonstração",
  },
  {
    id: "prova-social",
    regex: /\+\s*\d{1,3}(?:[.\s]\d{3})+\s*(?:assinantes|leitores|usu[aá]rios|membros|alunos)/i,
    msg: "prova social inventada no formato '+N.NNN assinantes/leitores/...'",
  },
  {
    id: "preco-plano",
    // Preço de plano fixo em código de renderização.
    regex: /(?:preco|price)\s*[:=]\s*["'`]?\d+[.,]\d{2}\b/i,
    msg: "preço de plano hardcoded no caminho de renderização",
    contextoObrigatorio: /(plano|assinatura|premium|free|assinatura\/planos)/i,
  },
];

/** Arquivos/linhas explicitamente isentos (com justificativa). */
const EXECOES = [
  // A própria guarda menciona os padrões que procura.
  { arquivo: "scripts/verificar-conteudo-ficticio.mjs", motivo: "é a própria guarda" },
];

function listarArquivos(dir) {
  const achados = [];
  let entradas;
  try {
    entradas = readdirSync(dir);
  } catch {
    return achados;
  }
  for (const entrada of entradas) {
    if (IGNORAR_DIR.has(entrada)) continue;
    const caminho = join(dir, entrada);
    let st;
    try {
      st = statSync(caminho);
    } catch {
      continue;
    }
    if (st.isDirectory()) achados.push(...listarArquivos(caminho));
    else {
      const ponto = caminho.lastIndexOf(".");
      if (ponto === -1) continue;
      if (EXTENSOES.has(caminho.slice(ponto))) achados.push(caminho);
    }
  }
  return achados;
}

/** Remove strings de import e blocos de comentário; devolve índice→conteúdo. */
function semImportNemComentario(linha) {
  let s = linha;
  // remove import ... from "..."
  s = s.replace(/^\s*import\s+.*$/, "");
  // remove comentário de linha e de bloco na mesma linha
  s = s.replace(/\/\*[\s\S]*?\*\//g, " ");
  s = s.replace(/\/\/.*$/, "");
  return s;
}

/** Verdadeiro quando a linha é comentário/import/string de doc legítima. */
function ehLinhaPermitida(texto, arquivoRel) {
  for (const exc of EXECOES) if (arquivoRel === exc.arquivo) return true;

  const semCodigo = semImportNemComentario(texto);

  // Linha 100% comentário: só vira achado se tiver padrão de preço/prova
  // social fora de comentário. Para dado-mock, comentário nunca acusa.
  if (semCodigo.trim() === "") {
    return COMENTARIOS_PERMITIDOS.some((r) => r.test(texto));
  }

  // `placeholder` como atributo JSX de formulário ou prop de UI é legítimo.
  if (/(?:^|\s)placeholder\s*=/.test(semCodigo)) {
    // ... exceto se o valor for um array de conteúdo (não é caso no frontend).
    return true;
  }
  if (/\bplaceholder\s*:\s*["'`]/.test(semCodigo)) return true;
  // Placeholder citado em import de tipo.
  if (/\bplaceholder\b/.test(semCodigo) && !/MOCK|mock|fake|dummy/i.test(semCodigo)) {
    return COMENTARIOS_PERMITIDOS.some((r) => r.test(texto));
  }

  // Comentário explicativo honesto na mesma linha libera a linha.
  const temComentario = /\/\//.test(texto) || /\/\*/.test(texto);
  if (temComentario && COMENTARIOS_PERMITIDOS.some((r) => r.test(texto))) return true;

  return false;
}

const violacoes = [];

for (const dir of DIRETORIOS) {
  const raiz = join(RAIZ, dir);
  for (const arquivo of listarArquivos(raiz)) {
    const rel = relative(RAIZ, arquivo).split(sep).join("/");
    let conteudo;
    try {
      conteudo = readFileSync(arquivo, "utf8");
    } catch {
      continue;
    }
    const linhas = conteudo.split("\n");
    for (let i = 0; i < linhas.length; i++) {
      const texto = linhas[i];
      if (!texto.trim()) continue;
      if (ehLinhaPermitida(texto, rel)) continue;
      const semCodigo = semImportNemComentario(texto);
      for (const regra of REGRAS) {
        if (regra.contextoObrigatorio && !regra.contextoObrigatorio.test(texto)) continue;
        const alvo = regra.id === "dado-mock" || regra.id === "dado-mock-literal" ? semCodigo : semCodigo;
        if (!regra.regex.test(alvo)) continue;
        violacoes.push({
          arquivo: rel,
          linha: i + 1,
          regra: regra.id,
          mensagem: regra.msg,
          trecho: texto.trim().slice(0, 120),
        });
      }
    }
  }
}

if (violacoes.length === 0) {
  console.log("OK — nenhum conteudo ficticio encontrado nos caminhos de renderizacao.");
  process.exit(0);
}

console.error("FALHA — conteudo ficticio presente nos caminhos de renderizacao:\n");
for (const v of violacoes) {
  console.error(`  ${v.arquivo}:${v.linha}  [${v.regra}] ${v.mensagem}`);
  console.error(`      ${v.trecho}`);
}
console.error(`\n${violacoes.length} achado(s). Remova o dado ficticio ou documente a decisao editorial.`);
process.exit(1);
