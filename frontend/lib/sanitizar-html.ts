/**
 * Sanitizador de HTML de conteúdo editorial, sem dependência externa.
 *
 * -------------------------------------------------------------------------
 * POR QUE NÃO USAR `dangerouslySetInnerHTML` COM HTML DE RSS
 * -------------------------------------------------------------------------
 * `resumo` de item do feed é texto puro do XML da fonte, mas `feedparser`
 * também aceita `<content:encoded>`/`<description>` com HTML completo. Se
 * esse HTML chegar cru ao `dangerouslySetInnerHTML`, é XSS armazenado
 * servido sob a origem do portal.
 *
 * -------------------------------------------------------------------------
 * POR QUE ESTE MÓDULO E NÃO `sanitize-html` / `DOMPurify`
 * -------------------------------------------------------------------------
 * O projeto roda em Node 20 e 22 (CI e Dockerfiles) sem jsdom, e
 * DOMPurify precisa de DOM. `sanitize-html` é a opção robusta, mas
 * adicionaria dependência de runtime a um portal que hoje tem zero
 * sanitizador. Este sanitizador é deliberadamente CONSERVADOR: em vez de
 * tentar列举 e bloquear tags perigosas (blacklist, sempre incompleta),
 * ele processa o HTML token a token e reconstrói a saída a partir de uma
 * ALLOWLIST. O que não está na allowlist é descartado — o default é
 * "não renderizar", não "não bloquear".
 *
 * Limite conhecido e aceito: a tokenização é por regex, não por parser
 * HTML completo (diferente de `html.parser` do Python, usado no lado do
 * backend com garantia equivalente). Ela foi desenhada para NÃO ser
 * enganável pelas construções de bypass clássicas (ver testes em
 * `testes/sanitizar-html.test.mjs`), mas um parser de verdade é
 * estritamente superior. Registrado como dívida, não escondido.
 *
 * A sanitização no backend (`backend/config/sanitizar_html.py`) é a
 * fronteira primária porque roda antes da persistência; esta é a segunda
 * camada, para o HTML que já está no banco ou chega por cache.
 */

/** Tags permitidas e o que fazer com cada uma. */
const TAGS_PERMITIDAS: Record<string, "fechar" | "ignorar-conteudo"> = {
  p: "fechar",
  br: "fechar",
  hr: "fechar",
  strong: "fechar",
  b: "fechar",
  em: "fechar",
  i: "fechar",
  u: "fechar",
  s: "fechar",
  sub: "fechar",
  sup: "fechar",
  h1: "fechar",
  h2: "fechar",
  h3: "fechar",
  h4: "fechar",
  h5: "fechar",
  h6: "fechar",
  ul: "fechar",
  ol: "fechar",
  li: "fechar",
  dl: "fechar",
  dt: "fechar",
  dd: "fechar",
  a: "fechar",
  blockquote: "fechar",
  pre: "fechar",
  code: "fechar",
  // Tags cujo conteúdo é INSEGURO no contexto do elemento: mantém o texto
  // legível, descarta a marcação. É o comportamento correto para
  // `<script>alert(1)</script>` — o leitor vê "alert(1)" como texto.
  script: "ignorar-conteudo",
  style: "ignorar-conteudo",
  iframe: "ignorar-conteudo",
  object: "ignorar-conteudo",
  embed: "ignorar-conteudo",
  template: "ignorar-conteudo",
  noscript: "ignorar-conteudo",
  svg: "ignorar-conteudo",
  math: "ignorar-conteudo",
};

/** Atributos permitidos por tag. */
const ATRIBUTOS_PERMITIDOS: Record<string, string[]> = {
  "*": ["title", "lang", "dir"],
  a: ["href", "title", "rel", "target", "lang", "dir"],
  ol: ["start", "type"],
  li: ["value"],
};

/** Esquemas de URL tolerados em `href`. */
const ESQUEMAS_HREF = new Set(["http:", "https:", "mailto:"]);

/** Atributos da allowlist que são boolean HTML legítimos (sem valor). */
const ATRIBUTOS_FLAG_BOOLEANOS = new Set(["hidden"]);

/** Remove o conteúdo (e as tags) de tudo que estiver dentro de uma tag
 *  marcada como "ignorar-conteudo". Faz isso ANTES da tokenização normal,
 *  porque `<script>var x = "</scr" + "ipt>"` é o bypass clássico. */
function descartarConteudoPerigoso(html: string): string {
  let saida = html;
  for (const tag of Object.keys(TAGS_PERMITIDAS)) {
    if (TAGS_PERMITIDAS[tag] !== "ignorar-conteudo") continue;
    // `[\s\S]*?` para atravessar novaslines; case-insensitive.
    const abertura = new RegExp(`<${tag}\\b[^>]*>`, "gi");
    const fechoSimples = new RegExp(`</${tag}\\s*>`, "gi");
    // 1) Tags sem fecho: remove da abertura até o fim.
    saida = saida.replace(abertura, (match, offset: number) => {
      // Se existe um fecho depois, deixa o par para o passo 2.
      const resto = saida.slice(offset + match.length);
      return fechoSimples.test(resto) ? "" : match;
    });
    // 2) Par completo: descarta o miolo.
    saida = saida.replace(
      new RegExp(`<${tag}\\b[^>]*>[\\s\\S]*?(?:</${tag}\\s*>|$)`, "gi"),
      "",
    );
  }
  return saida;
}

function escaparTexto(texto: string): string {
  return (
    texto
      .replace(/&(?![a-zA-Z][a-zA-Z0-9]{1,10};|#[0-9]{1,7};|#x[0-9a-fA-F]{1,6};)/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      // Aspas e apóstrofos são inofensivos em text node, mas esta saída
      // pode ser embutida num atributo por um chamando futuro; escapá-los
      // torna o texto seguro nos DOIS contextos. Custo zero.
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#x27;")
  );
}

function escaparAtributo(valor: string): string {
  return escaparTexto(valor).replace(/"/g, "&quot;").replace(/'/g, "&#x27;");
}

/** Valida e normaliza um `href`; devolve `null` se o esquema não for permitido. */
function hrefSeguro(valorBruto: string): string | null {
  // Remove controles C0 e DEL ANTES de parsear. É o que neutraliza o
  // bypass `java\tscript:alert(1)` — o browser ignora tab/CR/LF
  // dentro de uma URL, então só filtrar por substring não bastaria.
  // ESPAÇO (0x20) NÃO é removido de propósito: `new URL` o codifica
  // como %20, que é o comportamento correto (`java script:` vira URL
  // inválida e é rejeitada logo abaixo).
  const bruto = valorBruto.trim().replace(/[\u0000-\u001f\u007f]/g, "");
  if (!bruto) return null;
  let analisado: URL;
  try {
    analisado = new URL(bruto);
  } catch {
    // Relativas (ex.: "/politica") são resolvidas contra o site e inócuas.
    if (bruto.startsWith("/") && !bruto.startsWith("//")) return bruto;
    return null;
  }
  const protocolo = analisado.protocol.toLowerCase();
  if (!ESQUEMAS_HREF.has(protocolo)) return null;
  if (protocolo !== "mailto:" && (analisado.username || analisado.password)) return null;
  return analisado.toString();
}

/**
 * Sanitiza HTML editorial, devolvendo só marcação da allowlist.
 * Texto é sempre preservado (com escape); marcação fora da allowlist é
 * removida.
 */
export function sanitizarHtmlEditorial(entrada: unknown): string {
  if (typeof entrada !== "string" || !entrada) return "";

  // 1. Neutraliza blocos de conteúdo perigoso antes de qualquer outra coisa.
  const semPerigos = descartarConteudoPerigoso(entrada);

  const TAG_OU_COMENTARIO = /<!--[\s\S]*?-->|<!\[CDATA\[[\s\S]*?\]\]>|<!\w[^>]*>|<\/?([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[^>]*?)?)\/?>/g;

  let resultado = "";
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = TAG_OU_COMENTARIO.exec(semPerigos)) !== null) {
    resultado += escaparTexto(semPerigos.slice(cursor, match.index));
    cursor = match.index + match[0].length;

    // Comentário, CDATA ou declaration: descartados por inteiro.
    if (match[0].startsWith("<!") || match[0].startsWith("<!--")) continue;

    const nomeCru = (match[1] ?? "").toLowerCase();
    const ehFechamento = match[0].startsWith("</");
    const ehAutoFechada = match[0].endsWith("/>");

    // Tag não permitida (ex.: `img`, `form`, `marquee`): descarta a tag,
    // preserva o texto interno.
    if (!(nomeCru in TAGS_PERMITIDAS)) continue;
    if (TAGS_PERMITIDAS[nomeCru] === "ignorar-conteudo") continue;

    const atributos = ehFechamento ? {} : extrairAtributos(match[2] ?? "");
    const atributosLimpados = filtrarAtributos(nomeCru, atributos, ehAutoFechada);

    if (ehFechamento) {
      resultado += `</${nomeCru}>`;
    } else {
      const sufixo = ehAutoFechada ? " /" : "";
      const serializados = atributosLimpados
        .map(([chave, valor]) => (valor === null ? ` ${chave}` : ` ${chave}="${valor}"`))
        .join("");
      resultado += `<${nomeCru}${serializados}${sufixo}>`;
    }
  }
  resultado += escaparTexto(semPerigos.slice(cursor));
  return resultado;
}

/** Extrai `nome="valor"`, `nome='valor'`, `nome=valor` e flags soltas. */
function extrairAtributos(bruto: string): Record<string, string | null> {
  const saida: Record<string, string | null> = {};
  const REGEX = /([a-zA-Z_:][a-zA-Z0-9_.:-]*)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>=`]+)))?/g;
  let m: RegExpExecArray | null;
  while ((m = REGEX.exec(bruto)) !== null) {
    const nome = (m[1] ?? "").toLowerCase();
    if (nome in saida) continue; // duplicata: vence a primeira
    const valor = m[2] ?? m[3] ?? m[4];
    saida[nome] = valor === undefined ? null : valor;
  }
  return saida;
}

function filtrarAtributos(
  tag: string,
  atributos: Record<string, string | null>,
  ehAutoFechada: boolean,
): Array<[string, string | null]> {
  const permitidosGlobais = ATRIBUTOS_PERMITIDOS["*"] ?? [];
  const permitidosDaTag = ATRIBUTOS_PERMITIDOS[tag] ?? [];
  const saida: Array<[string, string | null]> = [];

  for (const [nome, valor] of Object.entries(atributos)) {
    // `on*` (handlers) nunca passam, mesmo que a allowlist fosse estendida.
    if (nome.startsWith("on")) continue;
    // `style` nunca passa: é um vetor de CSS injection/exfiltração
    // (`background:url(...)`, `position:fixed` para clickjacking).
    if (nome === "style") continue;
    // `src`, `srcset`, `data`, `formaction`, `xlink:href`... nunca passam.
    if (!permitidosDaTag.includes(nome) && !permitidosGlobais.includes(nome)) continue;

    if (nome === "href") {
      const seguro = hrefSeguro(valor ?? "");
      if (!seguro) continue;
      saida.push([nome, escaparAtributo(seguro)]);
      continue;
    }
    if (nome === "rel" && ehAutoFechada) continue;
    if (nome === "target") {
      // Só `_blank`; com `rel` forçado pelo chamador para noopener.
      if ((valor ?? "").toLowerCase() !== "_blank") continue;
    }
    if (valor === null) {
      // Atributo sem valor. Só se mantém se for um boolean HTML legítimo
      // da allowlist; o resto é descartado por segurança.
      if (ATRIBUTOS_FLAG_BOOLEANOS.has(nome)) saida.push([nome, null]);
      continue;
    }
    saida.push([nome, escaparAtributo(valor)]);
  }

  // Link externo com `target="_blank"` SEM `rel="noopener noreferrer"` é
  // reverse tabnabbing. Injeta o rel em vez de confiar no autor.
  if (tag === "a" && saida.some(([n]) => n === "target")) {
    const temRel = saida.some(([n, v]) => n === "rel" && (v ?? "").includes("noopener"));
    if (!temRel) {
      const idx = saida.findIndex(([n]) => n === "target");
      saida.splice(idx + 1, 0, ["rel", "noopener noreferrer nofollow"]);
    }
  }

  return saida;
}
