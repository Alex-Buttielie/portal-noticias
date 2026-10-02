// ===========================================================================
// PLACEHOLDER DE IMAGEM — GERADO LOCALMENTE, SEM SAIR DA MÁQUINA
// ===========================================================================
// O QUE ISTO É
// ===========
// Quando a notícia não tem `imagem_url` (ou a URL é recusada pela allowlist
// de esquema, ou aponta para o host do placeholder), o portal precisa de
// ALGUMA imagem no lugar. Este arquivo é o gerador desse "alguma imagem".
//
// O QUE ISTO NÃO É
// ================
// NÃO é uma requisição. A saída é um `data:image/svg+xml` embutido no
// próprio HTML: o browser não abre conexão nenhuma para desenhá-lo. É
// diferente do que o portal fazia antes, que pedia a foto a um host de
// TERCEIRO (`picsum.photos`) — 61 conexões na home, todas ANTES de
// qualquer consentimento (a medição, antes e depois, está em `imagens.ts`).
//
// A VARIAÇÃO, E POR QUE ELA SOBREVIVEU
// =====================================
// O `seed` do picsum existia por um motivo: sem ele, TODAS as notícias sem
// foto mostrariam a mesma imagem, e a home viraria um mar de cartões
// idênticos — impossível varrer a tela por assunto. A variação não pode ser
// perdida, e também não pode "piscar" (a mesma notícia precisa mostrar
// sempre a mesma imagem, senão a home muda a cada carregamento).
//
// Daí a escolha: em vez de escolher um arquivo entre N versionados (o que
// limitaria a variedade a N), o tom, a geometria do degradê, a textura e a
// inicial saem de um HASH DETERMINÍSTICO do identificador da notícia. O
// espaço de imagens é grande, é reprodutível byte a byte em qualquer
// máquina/processo, não depende de nenhum arquivo no disco, e o mesmo
// identificador devolve SEMPRE a mesma string.
//
// A ESCOLHA ENTRE AS SAÍDAS QUE A DECISÃO DE PRODUTO DEIXOU ABERTAS
// ====================================================================
// (a) conjunto pequeno de SVG versionados + hash para escolher um
//     -> variação limitada a N imagens: a home volta a ter poucas imagens
//        distintas, que é exatamente o que o `seed` existia para evitar.
//        N arquivos para versionar e ainda UMA REQUISIÇÃO por imagem.
// (b) placeholder único com inicial/categoria variando
// (c) imagem local + degradê/pattern que varia por hash
//     -> (b) e (c) juntos é o que está aqui: a inicial dá a pista do
//        assunto, o degradê e a textura dão a distinção entre duas
//        notícias DA MESMA categoria, e nada disso custa um arquivo nem uma
//        conexão.
//
// (a) foi descartada porque resolve a conexão e perde a variação. O preço
// de (b)+(c) é byte no HTML: um placeholder leva ~600-900 bytes embutido,
// contra 0 de requisição. Numa home com 41 placeholders são ~30 kB que
// descem JUNTO com o documento que a pessoa já está baixando — e o que
// sai do outro lado são 41 conexões, 41 resolutions de DNS e 41 handshakes
// TLS para um host de terceiro, que é o custo que a pendência existed to
// remove. Medido: ver `imagens.ts`.
// ===========================================================================

/**
 * Paleta do placeholder. São as MESMAS cores de `lib/categoryVisuals.ts`
 * (`#1c1917` → `#a8a29e`, o cinza-quente do portal): o placeholder precisa
 * parecer parte do produto, não um retângulo cinza genérico. Como o SVG é um
 * documento separado (data URI), ele não enxerga as CSS custom properties
 * do portal — daí as cores serem literais aqui, em `rgb()` para não gastar
 * byte com `#`.
 */
const PALETA: ReadonlyArray<readonly [number, number, number]> = [
  [28, 25, 23], // #1c1917
  [46, 42, 38], // #2e2a26
  [68, 64, 60], // #44403c
  [87, 83, 78], // #57534e
  [120, 113, 108], // #78716c
  [168, 162, 158], // #a8a29e
];

/**
 * Geometria do degradê, em % do viewBox (x1,y1 → x2,y2).
 *
 * São 8 e NÃO 360 ângulos de propósito: um degradê em ângulo aleatório fica
 * com cara de erro de render. Estas oito são todas "de um canto/lado para o
 * outro", que é o que o olho lê como fotografia desfocada.
 */
const GEOMETRIAS: ReadonlyArray<readonly [number, number, number, number]> = [
  [0, 0, 100, 100],
  [100, 0, 0, 100],
  [0, 100, 100, 0],
  [100, 100, 0, 0],
  [0, 0, 100, 45],
  [100, 0, 0, 45],
  [45, 0, 45, 100],
  [0, 45, 100, 45],
];

const L = 800;
const A = 450;

/**
 * Hash FNV-1a de 32 bits.
 *
 * Por que FNV-1a e não `hash * 31` (o de `categoryVisuals.ts`): o FNV-1a é
 * canônico e tem taxa de colisão medida; o `* 31` concentra em poucos bits e
 * faz identificadores diferentes cair na mesma imagem mais vezes do que o
 * acaso. Nenhum dos dois é criptográfico, e nenhum precisa ser — o
 * identificador da notícia não é segredo.
 *
 * Determinismo é o requisito, e `>>> 0` devolve sempre um inteiro de 32
 * bits sem sinal, igual em qualquer engine JS.
 */
function hash(texto: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < texto.length; i++) {
    h ^= texto.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

/**
 * Primeira letra visível da categoria, para o placeholder não ser um bloco
 * de cor sem nenhuma pista do assunto.
 *
 * SEGURANÇA: `categoria` vem do XML do RSS — conteúdo de terceiro — e esta
 * letra entra num SVG que vira `src` de `<img>`. Um `<script>` ou um
 * `onload=` aqui dentro seria execução no contexto do documento. Por isso o
 * filtro é explícito: só sai letra/número do alfabeto latino (e as
 * maiúsculas acentuadas, que o design usa), com UM caractere, e qualquer
 * coisa fora disso devolve string vazia e a letra simplesmente não é
 * desenhada. Categoria em cirílico, em chinês ou contendo HTML não produz
 * letra — produz placeholder sem letra, que é o comportamento seguro.
 */
function inicialDe(categoria: string): string {
  const primeira = Array.from(categoria.trim())[0] ?? "";
  return /^[A-Za-zÀ-ÖØ-öø-ÿ0-9]$/.test(primeira) ? primeira.toUpperCase() : "";
}

/**
 * Escapa o que tiver escapável. Com a lista de caracteres já filtrada em
 * `inicialDe` não há nada perigoso sobrando, mas a função fica aqui para
 * que uma alteração futura na lista não vire XSS em silêncio.
 */
function escapaXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/**
 * As 4 texturas. Cada uma é um `<pattern>` com UMA forma dentro e
 * `patternTransform` — o que mantém o SVG em ~1 kB em vez dos ~5 kB de um
 * equivalente com 60 `<circle>` escritos à mão.
 *
 * ASPAS SIMPLES em todos os atributos, de propósito: `encodeURIComponent`
 * NÃO codifica `'`, e codifica `"`. Trocar aspas simples por duplas custaria
 * ~2 bytes por atributo, e são ~30 atributos.
 */
function texturaSvg(indice: number, lado: number, giro: number, cor: string): string {
  const comum = `id='p' width='${lado}' height='${lado}' patternUnits='userSpaceOnUse' patternTransform='rotate(${giro})'`;
  switch (indice % 4) {
    case 0: // listras diagonais
      return `<pattern ${comum}><path d='M0 ${Math.round(lado / 2)}h${lado}' stroke='${cor}' stroke-width='6' stroke-opacity='.14'/></pattern>`;
    case 1: // pontos
      return `<pattern ${comum}><circle cx='${Math.round(lado / 2)}' cy='${Math.round(lado / 2)}' r='5' fill='${cor}' fill-opacity='.14'/></pattern>`;
    case 2: // faixas largas
      return `<pattern ${comum}><rect width='${lado}' height='${Math.max(4, Math.round(lado / 4))}' fill='${cor}' fill-opacity='.13'/></pattern>`;
    default: // anéis
      return `<pattern ${comum}><circle cx='${Math.round(lado / 2)}' cy='${Math.round(lado / 2)}' r='${Math.round(lado / 3)}' fill='none' stroke='${cor}' stroke-opacity='.16' stroke-width='4'/></pattern>`;
  }
}

/**
 * Gera o placeholder em SVG embutido (data URI).
 *
 * Determinístico: o mesmo `identificador` devolve SEMPRE a mesma string, em
 * qualquer máquina, qualquer processo, qualquer engine. É isso que o `seed`
 * do picsum fazia, e é o que impede a home de "piscar" entre carregamentos.
 *
 * @param identificador  `${categoria}-${id}` — a MESMA chave que era o `seed`
 * @param categoria      só para a inicial; já entra no identificador, mas
 *                       aqui deixa a letra óbvia
 */
export function placeholderSvg(identificador: string, categoria?: string): string {
  const id = identificador || "geral-0";
  const h = hash(id);
  const c1 = `rgb(${PALETA[h % PALETA.length].join(",")})`;
  const c2 = `rgb(${PALETA[(h >>> 3) % PALETA.length].join(",")})`;
  const g = GEOMETRIAS[(h >>> 5) % GEOMETRIAS.length];
  const textura = texturaSvg((h >>> 9) % 4, 40 + ((h >>> 13) % 60), (h >>> 19) % 90, c1);
  const letra = inicialDe(categoria ?? id.replace(/-\d+$/, ""));

  const svg =
    `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 ${L} ${A}'>` +
    `<defs><linearGradient id='f' x1='${g[0]}%' y1='${g[1]}%' x2='${g[2]}%' y2='${g[3]}%'>` +
    `<stop offset='0' stop-color='${c1}'/><stop offset='1' stop-color='${c2}'/>` +
    `</linearGradient>${textura}</defs>` +
    `<rect width='${L}' height='${A}' fill='url(#f)'/>` +
    `<rect width='${L}' height='${A}' fill='url(#p)'/>` +
    (letra
      ? `<text x='400' y='252' fill='${c1}' fill-opacity='.32' font-family='Georgia,serif' ` +
        `font-size='210' font-weight='700' text-anchor='middle'>${escapaXml(letra)}</text>`
      : "") +
    `</svg>`;

  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

/**
 * Placeholder da notícia, na MESMA forma de chamada que o `picsum(seed)`
 * tinha. É este o ponto único por onde o portal desenha "não há foto".
 */
export function placeholderNoticia(identificador: string, categoria?: string): string {
  return placeholderSvg(identificador, categoria);
}