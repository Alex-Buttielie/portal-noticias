import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { SITE_NAME, SITE_URL } from "@/lib/site";
import { obterPaginaEditorial } from "@/lib/api";
// P0-08: a distinção entre "a página não existe" e "a API não respondeu" é
// uma política testável, não um detalhe de um `catch`. Ver a razão de existir
// do arquivo antes de trocar o comportamento daqui.
import { classificarErroPaginaEditorial } from "@/lib/paginas-editoriais";
import { formatarDataCurta } from "@/lib/datas";
// P0-10 (eixo 1, XSS): sanitizador de allowlist para o HTML editorial.
import { sanitizarHtmlEditorial } from "@/lib/sanitizar-html";
// P0-08: estado de indisponibilidade REAL quando o backend não responde —
// em vez de inventar uma página para a tela não ficar vazia.
import { EstadoVazio } from "@/components/EstadoVazio";
export async function generateMetadata({params}:{params:Promise<{slug:string}>}): Promise<Metadata>{ const {slug}=await params; return { title: `${slug} - ${SITE_NAME}`, openGraph:{ title: slug, url: `${SITE_URL}/paginas/${slug}` } }; }
// SEM `generateStaticParams` — e a remoção é deliberada.
//
// O que ele declarava era `[{slug:"termos"}, {slug:"sobre"}]`. MEDIDO nos
// três bancos em 2026-10-08: `moderacao_PaginaEditorial` contém apenas
// `politica-editorial` e `termos-de-uso`. Nenhum dos dois slugs declarados
// existe.
//
// Com o `catch` que fabricava conteúdo (ver abaixo), isso passava despercebido:
// a página era pré-renderizada com "Conteúdo editorial para <termos> em
// preparação" e devolvia HTTP 200. Um 404 que se apresenta como 200 é pior que
// um 404, porque monitor e leitor confiam nos dois.
//
// Manter a lista com os slugs REAIS também não resolve: `next build` roda em
// dois lugares — o job `frontend-build` do CI, que não tem API, e o build de
// produção na VPS, que tem. No CI qualquer tratamento de erro aqui ou quebra o
// build (`notFound()` durante a geração estática) ou congela na página o que
// foi gerado. Sem `generateStaticParams` não há fetch no build: a rota passa a
// ser gerada sob demanda, com `dynamicParams` no padrão (true), que é o que
// `/paginas/<slug>` sempre foi na prática.
export const revalidate=60;
export default async function Page({params}:{params:Promise<{slug:string}>}){
  // P1-16b: `params` é uma Promise no Next 15 e precisa ser aguardada.
  const {slug}=await params;
  // P0-10: o slug vem da URL e é controlado por quem fez a requisição. Antes
  // ele era interpolado DIRETO numa string de HTML no caminho de fallback
  // (`<strong>${slug}</strong>`) e injetado via dangerouslySetInnerHTML —
  // XSS refletido sem nenhum dado externo. Aqui ele só é usado como React
  // child (escapado pelo React) e delimitado por uma allowlist de
  // caracteres.
  const slugSeguro = (slug || "").replace(/[^a-z0-9-]/gi, "").slice(0, 60);
  let pagina:any=null;
  // `erroApi` é a distinção que o código antigo não fazia. Um `catch` que
  // trata "a página não existe" e "a API está fora" do mesmo jeito é o que
  // permitia a fabricação: nos dois casos ele inventava uma página.
  let erroApi=false;
  try{
    pagina=await obterPaginaEditorial(slug);
  }catch(e){
    // 404 é o backend AFIRMANDO que o slug não existe. Aí a resposta certa é
    // 404, e é a única coisa que devolve.
    if (classificarErroPaginaEditorial(e) === "inexistente") notFound();
    // Qualquer outra falha (API fora do ar, 5xx, timeout, DNS) NÃO é prova de
    // que a página não existe — e também não autoriza fabricar conteúdo. O
    // padrão de honestidade é o mesmo de `/categoria/[slug]`: estado de erro
    // real, dizendo que nada foi inventado.
    erroApi=true;
  }
  if(erroApi){
    return (<div className="mx-auto max-w-3xl space-y-4 py-6"><div className="hud-line mb-4" aria-hidden /><EstadoVazio tom="erro" titulo="Não foi possível carregar esta página" descricao="O serviço editorial não respondeu. Nenhum conteúdo foi inventado para preencher a página." acao={{rotulo:"Ver institucional",href:"/sobre"}} /></div>);
  }
  // P0-10: `pagina.conteudo` é HTML vindo do backend (`moderacao.PaginaEditorial`,
  // editável pelo admin). Passe sempre pelo sanitizador antes de injetar:
  // o default é allowlist de tags/atributos, então `<script>`, handlers
  // `on*`, `<iframe>`, `style=` e `javascript:` não passam. A segunda
  // camada (backend) não substitui esta: o HTML também pode chegar de
  // cache/CDN já persistido antes desta validação existir.
  const conteudoSeguro = sanitizarHtmlEditorial(pagina?.conteudo);
  const titulo = typeof pagina?.titulo === "string" && pagina.titulo ? pagina.titulo : (slugSeguro || "Página");
  return (<div className="mx-auto max-w-3xl space-y-4 py-6"><div className="hud-line mb-4" aria-hidden /><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="prose max-w-none p-6 prose-headings:text-[var(--cor-texto)] prose-p:text-[var(--cor-texto-suave)]"><h1 className="capitalize text-[var(--cor-texto)]">{titulo}</h1><div dangerouslySetInnerHTML={{__html: conteudoSeguro}} /><p className="text-xs text-[var(--cor-texto-suave)]">Atualizado em {formatarDataCurta(pagina.atualizado_em)}</p></CardContent></Card></div>);
}