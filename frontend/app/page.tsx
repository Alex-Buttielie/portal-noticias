import type { Metadata } from "next";
import { SITE_DESCRIPTION, SITE_NAME } from "@/lib/site";
import { obterDestaquesDia, obterFeed, obterMaisLidas, obterUrgentes, type EntradaRanqueda, type FeedEntrada } from "@/lib/api";
import { carregarHome } from "@/lib/recomendacao";
import { carregarColunistas, type Colunista } from "@/lib/colunistas";
import { HomeClient } from "@/components/HomeClient";
import { DestaquesDia } from "@/components/DestaquesDia";

export const metadata: Metadata = {
  title: SITE_NAME,
  description: SITE_DESCRIPTION,
};

export const revalidate = 60;

// Densidade editorial da Home: busca página cheia do backend (page_size 60)
// para alimentar Manchetes + Últimas + Em Alta + Bombando + Portfólio sem
// limite arbitrário pequeno no cliente.
const PAGE_SIZE_HOME = 60;

const MOCK: FeedEntrada[] = [
  { tipo: "cluster", id: 1, titulo: "Mercados reagem a novo ciclo de juros com volatilidade contida", resumo: "Analistas projetam estabilidade após sinalização do banco central.", categoria: "economia", urgente: true, numero_fontes: 4, timestamp: new Date().toISOString(), cidade: "São Paulo", estado: "SP", pais: "Brasil", nome_fonte: "Redação" },
  { tipo: "item", id: 2, titulo: "Tecnologia quântica ganha protótipo nacional", resumo: "Pesquisadores anunciam avanço em computação de baixa temperatura.", categoria: "tecnologia", urgente: false, numero_fontes: 3, timestamp: new Date().toISOString(), nome_fonte: "Redação" },
  { tipo: "cluster", id: 3, titulo: "Clima extremo mobiliza capitais do Sudeste", resumo: "Defesa civil emite alerta para chuvas intensas nas próximas 48h.", categoria: "cidades", urgente: true, numero_fontes: 5, timestamp: new Date().toISOString(), estado: "SP", pais: "Brasil", nome_fonte: "Redação" },
  { tipo: "item", id: 4, titulo: "Seleção confirma amistosos antes das eliminatórias", resumo: "Comissão técnica testa novas formações no meio-campo.", categoria: "esportes", urgente: false, numero_fontes: 2, timestamp: new Date().toISOString(), pais: "Brasil", nome_fonte: "Redação" },
  { tipo: "item", id: 5, titulo: "Festival ocupa centro histórico com arte imersiva", resumo: "Instalações de luz e som transformam praças em galerias a céu aberto.", categoria: "cultura", urgente: false, numero_fontes: 2, timestamp: new Date().toISOString(), cidade: "Goiânia", estado: "GO", pais: "Brasil", nome_fonte: "Redação", autor: "Colunista Convidada" },
  { tipo: "item", id: 6, titulo: "Saúde amplia cobertura vacinal em 12 capitais", resumo: "Campanha mira público jovem com postos volantes.", categoria: "saúde", urgente: false, numero_fontes: 3, timestamp: new Date().toISOString(), nome_fonte: "Redação" },
];

async function getData() {
  try {
    // FRENTE 3 — feed ranqueado pelo backend (curadoria/popularidade/
    // personalização/tendência/recência + overrides, sem repetição).
    const [home, urg, lidas, destaques, colunistas] = await Promise.all([
      carregarHome(10),
      obterUrgentes(8).catch(() => [] as FeedEntrada[]),
      obterMaisLidas(10).catch(() => [] as FeedEntrada[]),
      obterDestaquesDia({ limite: 5 }).catch(() => [] as EntradaRanqueda[]),
      carregarColunistas(4),
    ]);
    let lista = home.feed.length ? home.feed : MOCK;
    if (!home.feed.length) {
      const feed = await obterFeed({ page_size: PAGE_SIZE_HOME }).catch(() => null);
      if (feed?.results?.length) lista = feed.results;
    }
    return {
      feed: lista,
      urg: urg.length ? urg : lista.filter((x) => x.urgente),
      maisLidas: lidas.length ? lidas : [],
      destaques,
      colunistas,
    };
  } catch {
    return {
      feed: MOCK,
      urg: MOCK.filter((x) => x.urgente),
      maisLidas: [] as FeedEntrada[],
      destaques: [] as EntradaRanqueda[],
      colunistas: [] as Colunista[],
    };
  }
}

export default async function Page() {
  const { feed, urg, maisLidas, destaques, colunistas } = await getData();
  return (
    <>
      <DestaquesDia destaques={destaques} />
      <HomeClient feed={feed} urg={urg} maisLidas={maisLidas} colunistas={colunistas} />
    </>
  );
}
