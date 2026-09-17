import type { Metadata } from "next";
import { SITE_DESCRIPTION, SITE_NAME } from "@/lib/site";
import { obterFeed, obterMaisLidas, obterUrgentes, type FeedEntrada } from "@/lib/api";
import { HomeClient } from "@/components/HomeClient";

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
    const [feed, urg, lidas] = await Promise.all([
      obterFeed({ page_size: PAGE_SIZE_HOME }),
      obterUrgentes(8).catch(() => [] as FeedEntrada[]),
      obterMaisLidas(10).catch(() => [] as FeedEntrada[]),
    ]);
    const lista = feed.results?.length ? feed.results : MOCK;
    return {
      feed: lista,
      urg: urg.length ? urg : lista.filter((x) => x.urgente),
      maisLidas: lidas.length ? lidas : [],
    };
  } catch {
    return { feed: MOCK, urg: MOCK.filter((x) => x.urgente), maisLidas: [] as FeedEntrada[] };
  }
}

export default async function Page() {
  const { feed, urg, maisLidas } = await getData();
  return <HomeClient feed={feed} urg={urg} maisLidas={maisLidas} />;
}
