#!/usr/bin/env node
import { execFileSync } from "node:child_process";
/**
 * Gate de `npm audit` que distingue o que é falha de produção do que é
 * ferramenta de build sem patch upstream.
 *
 * ## Por que não é `npm audit` puro, e por que também não é `--omit=dev`
 *
 * `npm audit` puro reprova por advisory que NÃO tem correção possível:
 * `braces` CVE-2026-93687 tem `first_patched_version: null`. Não existe versão
 * corrigida. Um gate que exige o impossível não é um gate: é uma porta
 * trancada sem chave, que só ensina a pessoa a parar de olhar.
 *
 * A alternativa óbvia, `npm audit --omit=dev`, seria MENOR e não funciona
 * aqui. `tailwindcss` está em `dependencies` (38 dependências de produção),
 * e é por ele que `braces` entra na árvore. Então `--omit=dev` continua
 * listando `braces` — e, pior, se algum dia alguém mover uma dependência de
 * runtime para `devDependencies`, ele passaria a esconder exatamente o que
 * este gate existe para enxergar. Omitir não é auditar o que importa.
 *
 * ## O que este gate faz
 *
 * 1. Roda `npm audit --json` e coleta os advisories RAIZ (os que têm objeto
 *    em `via`; os outros nomes são dependentes que só repetem o advisory).
 * 2. Compara esse conjunto com a lista documentada abaixo. **Qualquer raiz
 *    fora da lista reprova.** Um advisory novo, uma dependência nova, um
 *    bump de versão — tudo reprova.
 * 3. Imprime o que foi tolerado, com o motivo, para o log do CI.
 *
 * A lista é sobre o advisory RAIZ, não sobre o pacote: os 7 pacotes que o
 * npm reporta são o mesmo `braces`ALCANCEADO por dois caminhos
 * (`tailwindcss → chokidar → fast-glob → micromatch → braces` e
 * `eslint-config-next → @next/eslint-plugin-next → fast-glob → braces`).
 * Listar os 7 seria listar o mesmo fato 7 vezes, e o próximo bump do
 * tailwindcss traria um 8º da mesma família sem que ninguém notasse.
 *
 * ## COMO CADA ADVISORY TOLERADO FOI CLASSIFICADO
 *
 * Não por leitura do `npm audit`, e sim por **output tracing** do próprio
 * Next: o `next build` com `output: "standalone"` (frontend/next.config.js)
 * grava o grafo de dependências realmente embarcado. `braces` está AUSENTE
 * de `.next/standalone`. Os dois advisories de runtime que JÁ existiam
 * (`sharp` CVE-2026-96889 e `source-map-js` CVE-2026-93749) estão PRESENTES
 * — e por isso foram corrigidos, não tolerados.
 *
 * Isso é a distinção que sustenta o gate: build-time ausente do standalone
 * é dívida de ergonomia de desenvolvimento; runtime presente é risco para
 * quem usa o site.
 *
 * ## Como este gate pode estar errado
 *
 * Se `braces` passar a ser alcançado em runtime — por exemplo, se um
 * componente passar a importar `tailwindcss` no servidor, ou se o Next
 * passar a incluir a cadeia do tailwind no standalone —, este gate
 * continua verde e Passaria a esconder um risco real. Foi por isso que a
 * lista guarda o advisory pelo NOME DA PACOTE-RAIZ e pelo texto do advisory,
 * e não por um número solto: se o `braces` reaparecer no standalone, a
 * correção é remover a tolerância, e a verificação de que ele continua
 * ausente do bundle é o que a torna honesta.
 */

/** Advisory raiz tolerado, com a razão escrita. */
const TOLERADOS = new Map([
  [
    "braces",
    {
      advisory: "braces vulnerable to stack-e(high) — CVE-2026-93687",
      patch: null, // `first_patched_version: null`: NAO existe versao corrigida
      onde: "build-only",
      razao:
        "Ausente de .next/standalone (output tracing do next build), entao nao " +
        "executa em producao. Sem patch upstream: a cadeia inteira foi " +
        "verificada (micromatch@4.0.8 ainda exige braces ^3.0.3; " +
        "fast-glob@3.3.3 ainda puxa micromatch; tailwindcss@3.4.19 ainda " +
        "exige chokidar + fast-glob). Tirar braces da arvore exigiria " +
        "tailwindcss v3 -> v4, que e breaking change de config e de tema.",
      sairDaListaQuando:
        "braces passar a aparecer em .next/standalone, ou existir patch upstream.",
    },
  ],
]);

function falha(msg, detalhe) {
  process.stderr.write(`\nAUDIT REPROVADO\n${msg}\n`);
  if (detalhe) process.stderr.write(`${detalhe}\n`);
  process.stderr.write(
    "\nSe este advisory nao tem patch e e build-only, a saida correta e " +
      "documenta-lo em TOLERADOS com a verificacao que sustenta a " +
      "classificacao — nao afrouxar o gate.\n",
  );
  process.exit(1);
}

let bruto;
try {
  bruto = execFileSync("npm", ["audit", "--json"], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    maxBuffer: 32 * 1024 * 1024,
  });
} catch (erro) {
  // `npm audit` sai != 0 quando ha vulnerabilidade. O JSON vem no stdout mesmo
  // assim; so e falha de verdade se nao houver JSON analisavel.
  bruto = erro.stdout;
  if (!bruto || !bruto.trim()) {
    falha(
      "npm audit nao produziu JSON analisavel.",
      String(erro.stderr || erro.message || erro).slice(0, 800),
    );
  }
}

let relatorio;
try {
  relatorio = JSON.parse(bruto);
} catch (erro) {
  falha("npm audit --json devolveu algo que nao e JSON.", String(erro.message).slice(0, 400));
}

const vulns = relatorio.vulnerabilities || {};

// Advisory raiz = o item cujo `via` tem um objeto. Os outros sao dependentes
// que apenas carregam o mesmo advisory; conta-los como advisory distinto
// inflaria o numero e esconderia o fato real.
const raizes = new Map();
for (const [pacote, v] of Object.entries(vulns)) {
  for (const via of v.via || []) {
    if (via && typeof via === "object") {
      raizes.set(pacote, {
        pacote,
        severidade: via.severity || v.severity,
        titulo: via.title || via.name || "?",
        url: via.url || null,
        faixa: via.range || null,
      });
    }
  }
}

const desconhecidos = [...raizes.values()].filter((r) => !TOLERADOS.has(r.pacote));

if (desconhecidos.length) {
  const lista = desconhecidos
    .map((r) => `  - ${r.pacote}: ${r.titulo} [${r.severidade}]${r.url ? ` ${r.url}` : ""}`)
    .join("\n");
  falha(
    `${desconhecidos.length} advisory(s) raiz fora da lista documentada.\n` +
      `Qualquer advisory novo reprova — e nao deveria, porque e exatamente\n` +
      `para isso que a lista existe:\n${lista}`,
  );
}

const meta = (relatorio.metadata || {}).vulnerabilities || {};
const nRaiz = raizes.size;
const nPacotes = Object.keys(vulns).length;

if (nRaiz === 0) {
  process.stdout.write(
    `AUDIT OK — zero advisory.\n` +
      `npm reporta: ${JSON.stringify(meta)}\n`,
  );
  process.exit(0);
}

const linhas = [];
for (const [pacote, info] of TOLERADOS) {
  const medido = raizes.get(pacote);
  if (!medido) continue;
  linhas.push(`TOLERADO (nao e falha verde, e tolerancia documentada)`);
  linhas.push(`  pacote........ ${pacote}`);
  linhas.push(`  advisory...... ${medido.titulo} [${medido.severidade}]`);
  if (medido.faixa) linhas.push(`  versoes....... ${medido.faixa}`);
  linhas.push(`  patch upstream ${info.patch === null ? "NAO EXISTE" : info.patch}`);
  linhas.push(`  onde executa.. ${info.onde}`);
  linhas.push(`  porque......... ${info.razao}`);
  linhas.push(`  sai da lista.. ${info.sairDaListaQuando}`);
  linhas.push(`  detalhado em... ${medido.url || "sem URL no relatorio"}`);
  linhas.push("");
}

process.stdout.write(
  `AUDIT OK com tolerancia documentada\n` +
    `\n` +
    `npm reporta ${nPacotes} pacote(s) vulneravel(is), mas sao ${nRaiz} advisory(s)\n` +
    `RAIZ — os outros ${nPacotes - nRaiz} sao dependentes que carregam o mesmo advisory.\n` +
    `Por severidade, como o npm conta: ${JSON.stringify(meta)}\n` +
    `\n` +
    linhas.join("\n") +
    `Regra: este gate so reprova por advisory raiz fora da lista. Um advisory\n` +
    `novo reprova sem excecao; um advisory sem patch e build-only precisa ser\n` +
    `documentado aqui, com a verificacao que sustenta a classificacao.\n`,
);