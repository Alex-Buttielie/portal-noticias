import type { Metadata } from "next";
import { Card, CardContent } from "@/components/ui/card";
import { SITE_NAME, SITE_URL } from "@/lib/site";
import { obterPaginaEditorial } from "@/lib/api";
import { formatarDataCurta } from "@/lib/datas";
import { sanitizarHtmlEditorial } from "@/lib/sanitizar-html";

export async function generateMetadata({params}:{params:{slug:string}}): Promise<Metadata>{ return { title: `${params.slug} - ${SITE_NAME}`, openGraph:{ title: params.slug, url: `${SITE_URL}/paginas/${params.slug}` } }; }
export function generateStaticParams(){ return [{slug:"termos"}, {slug:"sobre"}]; }
export const revalidate=60;
export default async function Page({params}:{params:{slug:string}}){
  // O slug vem da URL e é controlado por quem fez a requisição. Antes ele
  // era interpolado DIRETO numa string de HTML no caminho de fallback
  // (`<strong>${params.slug}</strong>`) e injetado via
  // dangerouslySetInnerHTML — XSS refletido sem nenhum dado externo.
  // Aqui ele só é usado como React child (escapado pelo React) e
  // delimitado por uma allowlist de caracteres.
  const slugSeguro = (params.slug || "").replace(/[^a-z0-9-]/gi, "").slice(0, 60);
  let pagina:any=null;
  try{ pagina=await obterPaginaEditorial(params.slug);}
  catch{ pagina={titulo: slugSeguro || "Página", conteudo:`<p>Conteúdo editorial para <strong>${slugSeguro}</strong> em preparação.</p>`, atualizado_em: new Date().toISOString()}; }
  // `pagina.conteudo` é HTML vindo do backend (`moderacao.PaginaEditorial`,
  // editável pelo admin). Passe sempre pelo sanitizador antes de injetar:
  // o default é allowlist de tags/atributos, então `<script>`, handlers
  // `on*`, `<iframe>`, `style=` e `javascript:` não passam. A segunda
  // camada (backend) não substitui esta: o HTML também pode chegar de
  // cache/CDN já persistido antes desta validação existir.
  const conteudoSeguro = sanitizarHtmlEditorial(pagina?.conteudo);
  const titulo = typeof pagina?.titulo === "string" && pagina.titulo ? pagina.titulo : (slugSeguro || "Página");
  return (<div className="mx-auto max-w-3xl space-y-4 py-6"><div className="hud-line" aria-hidden /><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="prose max-w-none p-6 prose-headings:text-[var(--cor-texto)] prose-p:text-[var(--cor-texto-suave)]"><h1 className="capitalize text-[var(--cor-texto)]">{titulo}</h1><div dangerouslySetInnerHTML={{__html: conteudoSeguro}} /><p className="text-xs text-[var(--cor-texto-suave)]">Atualizado em {formatarDataCurta(pagina.atualizado_em)}</p></CardContent></Card></div>);
}
