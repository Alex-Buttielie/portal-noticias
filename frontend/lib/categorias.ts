/**
 * Editorias e subcategorias — curadoria editorial fixa (o backend usa
 * `categoria` como texto livre, então o mapa vive aqui e os links de
 * subcategoria apontam para a busca `/buscar?q=termo`).
 */

export interface Subcategoria {
  nome: string;
  termo: string;
}

export interface Categoria {
  slug: string;
  nome: string;
  descricao: string;
  subcategorias: Subcategoria[];
}

function sub(nomes: string[]): Subcategoria[] {
  return nomes.map((nome) => ({ nome, termo: nome.toLowerCase() }));
}

export const CATEGORIAS: Categoria[] = [
  { slug: "política", nome: "Política", descricao: "Poder, eleições e bastidores.", subcategorias: sub(["Eleições", "Congresso", "Governo", "Justiça", "Partidos"]) },
  { slug: "economia", nome: "Economia", descricao: "Mercados, negócios e finanças.", subcategorias: sub(["Mercados", "Juros", "Inflação", "Negócios", "Emprego"]) },
  { slug: "tecnologia", nome: "Tecnologia", descricao: "Inovação, IA e produto.", subcategorias: sub(["Inteligência artificial", "Startups", "Gadgets", "Segurança digital", "Games"]) },
  { slug: "esportes", nome: "Esportes", descricao: "Jogos, clubes e bastidores.", subcategorias: sub(["Futebol", "Basquete", "Olimpíadas", "Fórmula 1", "Vôlei"]) },
  { slug: "cultura", nome: "Cultura", descricao: "Arte, música e cena.", subcategorias: sub(["Cinema", "Música", "Literatura", "Teatro", "Arte"]) },
  { slug: "saúde", nome: "Saúde", descricao: "Ciência, bem-estar e SUS.", subcategorias: sub(["Bem-estar", "Vacinas", "Nutrição", "Saúde mental", "SUS"]) },
  { slug: "mundo", nome: "Mundo", descricao: "Geopolítica e correspondentes.", subcategorias: sub(["América Latina", "Europa", "Estados Unidos", "Ásia", "Clima global"]) },
  { slug: "cidades", nome: "Cidades", descricao: "Mobilidade, clima e serviço.", subcategorias: sub(["Mobilidade", "Moradia", "Segurança", "Clima", "Serviços"]) },
];

export const SLUGS_CATEGORIAS = CATEGORIAS.map((c) => c.slug);

export function obterCategoria(slug: string): Categoria | undefined {
  const chave = (slug || "").trim().toLowerCase();
  return CATEGORIAS.find((c) => c.slug === chave);
}

export function hrefSubcategoria(sub: Subcategoria): string {
  return `/buscar?q=${encodeURIComponent(sub.termo)}`;
}

const STOPWORDS = new Set(
  "a ao aos aquela aquelas aquele aqueles as até com como contra da das de do dos e ela elas ele eles em entre era eram essa essas esse esses esta estas este estes foi foram há isso isto já lhe lhes mas me meu meus minha minhas muito na nas nem no nos nova novas novo novos nunca o os ou para pela pelas pelo pelos por qual quando que quem se sem ser seu seus sobre sua suas talvez tem têm ter tudo um uma vai vão ver vez vez você".split(" ")
);

export interface TopicoVivo extends Subcategoria {
  viva: true;
  ocorrencias: number;
}

/** Tópicos vivos: termos mais frequentes nos títulos das notícias da
 *  editoria (fixas mantidas + vivas por ocorrência, sem duplicar). */
export function extrairTopicosVivos(
  itens: { titulo: string; categoria: string }[],
  slug: string,
  max = 4
): TopicoVivo[] {
  const chave = (slug || "").trim().toLowerCase();
  const fixas = new Set(
    (obterCategoria(chave)?.subcategorias || []).map((s) => s.termo.toLowerCase())
  );
  const contagem = new Map<string, { nome: string; n: number }>();
  for (const item of itens || []) {
    if ((item.categoria || "").toLowerCase() !== chave) continue;
    const palavras = (item.titulo || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .split(/[^a-z0-9]+/);
    for (const p of palavras) {
      if (p.length < 4 || STOPWORDS.has(p) || fixas.has(p)) continue;
      const atual = contagem.get(p);
      contagem.set(p, { nome: p.charAt(0).toUpperCase() + p.slice(1), n: (atual?.n || 0) + 1 });
    }
  }
  return [...contagem.entries()]
    .filter(([, v]) => v.n >= 2)
    .sort((a, b) => b[1].n - a[1].n)
    .slice(0, max)
    .map(([termo, v]) => ({ nome: v.nome, termo, viva: true as const, ocorrencias: v.n }));
}

/** Fixas + vivas (vivas marcadas com `viva: true`). */
export function subcategoriasCompletas(
  slug: string,
  itens: { titulo: string; categoria: string }[] = []
): (Subcategoria | TopicoVivo)[] {
  const cat = obterCategoria(slug);
  if (!cat) return [];
  const vivas = extrairTopicosVivos(itens, slug);
  const termosFixos = new Set(cat.subcategorias.map((s) => s.termo.toLowerCase()));
  return [...cat.subcategorias, ...vivas.filter((v) => !termosFixos.has(v.termo.toLowerCase()))];
}
