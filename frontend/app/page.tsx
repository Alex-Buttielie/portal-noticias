import type { Metadata } from "next";
import { SITE_DESCRIPTION, SITE_NAME } from "@/lib/site";
import { obterDestaquesDia, obterFeed, obterMaisLidas, obterUrgentes, type EntradaRanqueda, type FeedEntrada } from "@/lib/api";
import { carregarHome } from "@/lib/recomendacao";
import { carregarColunistas, type Colunista } from "@/lib/colunistas";
import { HomeClient } from "@/components/HomeClient";
import { DestaquesDia } from "@/components/DestaquesDia";
import { EstadoVazio } from "@/components/EstadoVazio";

export const metadata: Metadata = {
  title: SITE_NAME,
  description: SITE_DESCRIPTION,
};

export const revalidate = 60;

// Densidade editorial da Home: busca página cheia do backend (page_size 60)
// para alimentar Manchetes + Últimas + Em Alta + Bombando + Portfólio sem
// limite arbitrário pequeno no cliente.
const PAGE_SIZE_HOME = 60;

// P0-08: a Home nunca fabrique notícia. Se as fontes vierem vazias ou
// falharem, a página renderiza um estado vazio explícito (ver EstadoVazio).
type DadosHome = {
  feed: FeedEntrada[];
  urg: FeedEntrada[];
  maisLidas: FeedEntrada[];
  destaques: EntradaRanqueda[];
  colunistas: Colunista[];
};

const SEM_DADOS: DadosHome = {
  feed: [],
  urg: [],
  maisLidas: [],
  destaques: [],
  colunistas: [],
};

async function getData(): Promise<DadosHome> {
  try {
    // FRENTE 3 — feed ranqueado pelo backend (curadoria/popularidade/
    // personalização/tendência/recência + overrides, sem repetição).
    const [home, urg, lidas, destaques, colunistas] = await Promise.all([
      carregarHome(10).catch(() => null),
      obterUrgentes(8).catch(() => [] as FeedEntrada[]),
      obterMaisLidas(10).catch(() => [] as FeedEntrada[]),
      obterDestaquesDia({ limite: 5 }).catch(() => [] as EntradaRanqueda[]),
      carregarColunistas(4).catch(() => [] as Colunista[]),
    ]);
    if (!home) return SEM_DADOS;
    let lista = home.feed;
    if (!lista.length) {
      const feed = await obterFeed({ page_size: PAGE_SIZE_HOME }).catch(() => null);
      lista = feed?.results ?? [];
    }
    return {
      feed: lista,
      urg: urg.length ? urg : lista.filter((x) => x.urgente),
      maisLidas: lidas,
      destaques,
      colunistas,
    };
  } catch {
    return SEM_DADOS;
  }
}

export default async function Page() {
  const { feed, urg, maisLidas, destaques, colunistas } = await getData();
  if (!feed.length) {
    return (
      <div className="space-y-6">
        <DestaquesDia destaques={destaques} />
        <EstadoVazio
          titulo="Nenhuma notícia disponível agora"
          descricao="A redação ainda não publicou manchetes, ou o serviço de notícias está temporariamente indisponível. Não vamos preencher a tela com conteúdo inventado."
          acao={{ rotulo: "Ver arquivo", href: "/arquivo" }}
        />
      </div>
    );
  }
  return (
    <>
      <DestaquesDia destaques={destaques} />
      <HomeClient feed={feed} urg={urg} maisLidas={maisLidas} colunistas={colunistas} />
    </>
  );
}
