import type { Metadata } from "next";
import { SITE_DESCRIPTION, SITE_NAME } from "@/lib/site";
import { obterFeed, obterUrgentes, type FeedEntrada } from "@/lib/api";
import { HomeClient } from "@/components/HomeClient";

export const metadata: Metadata = {
  title: SITE_NAME,
  description: SITE_DESCRIPTION,
};

export const revalidate = 60;

const MOCK: FeedEntrada[] = [
  { tipo: "cluster", id: 1, titulo: "Mercados reagem a novo ciclo de juros com volatilidade contida", resumo: "Analistas projetam estabilidade após sinalização do banco central.", categoria: "economia", urgente: true, numero_fontes: 4, timestamp: new Date().toISOString() },
  { tipo: "item", id: 2, titulo: "Tecnologia quântica ganha protótipo nacional", resumo: "Pesquisadores anunciam avanço em computação de baixa temperatura.", categoria: "tecnologia", urgente: false, numero_fontes: 3, timestamp: new Date().toISOString() },
  { tipo: "cluster", id: 3, titulo: "Clima extremo mobiliza capitais do Sudeste", resumo: "Defesa civil emite alerta para chuvas intensas nas próximas 48h.", categoria: "cidades", urgente: true, numero_fontes: 5, timestamp: new Date().toISOString() },
  { tipo: "item", id: 4, titulo: "Seleção confirma amistosos antes das eliminatórias", resumo: "Comissão técnica testa novas formações no meio-campo.", categoria: "esportes", urgente: false, numero_fontes: 2, timestamp: new Date().toISOString() },
  { tipo: "item", id: 5, titulo: "Festival ocupa centro histórico com arte imersiva", resumo: "Instalações de luz e som transformam praças em galerias a céu aberto.", categoria: "cultura", urgente: false, numero_fontes: 2, timestamp: new Date().toISOString() },
  { tipo: "item", id: 6, titulo: "Saúde amplia cobertura vacinal em 12 capitais", resumo: "Campanha mira público jovem com postos volantes.", categoria: "saúde", urgente: false, numero_fontes: 3, timestamp: new Date().toISOString() },
];

async function getData() {
  try {
    const [feed, urg] = await Promise.all([obterFeed({}), obterUrgentes(4).catch(() => [] as FeedEntrada[])]);
    return { feed: feed.results?.length ? feed.results : MOCK, urg: urg.length ? urg : MOCK.filter((x) => x.urgente) };
  } catch {
    return { feed: MOCK, urg: MOCK.filter((x) => x.urgente) };
  }
}

export default async function Page() {
  const { feed, urg } = await getData();
  return <HomeClient feed={feed} urg={urg} />;
}
