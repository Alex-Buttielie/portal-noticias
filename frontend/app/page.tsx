"use client";

import { Suspense, useEffect, useId, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as api from "@/lib/api";
import * as intencao from "@/lib/intent";
import * as bookmarks from "@/lib/bookmarks";
import { obterVisualCategoria } from "@/lib/categoryVisuals";
import CartaoEsqueleto from "@/components/CartaoEsqueleto";
import PorQueEstouVendoIsso from "@/components/PorQueEstouVendoIsso";
import BotaoSalvar from "@/components/BotaoSalvar";
import Chip from "@/components/Chip";
import Badge from "@/components/Badge";
import TickerUrgente from "@/components/TickerUrgente";
import MaisLidas from "@/components/MaisLidas";
import BlocoEditoria from "@/components/BlocoEditoria";

const CATEGORIAS_REFERENCIA = ["política","economia","esportes","tecnologia","saúde","cultura","cidades","mundo","ciência"];
const ATRASO_BUSCA_MS = 400;
const INTERVALO_VERIFICACAO_NOVIDADES_MS = 60000;

function formatarData(timestamp: string): string {
  try { return new Date(timestamp).toLocaleString("pt-BR", { day:"2-digit", month:"2-digit", hour:"2-digit", minute:"2-digit"});} catch { return timestamp; }
}
function chaveDaEntrada(e: api.FeedEntrada): string { return `${e.tipo}-${e.id}`; }
function motivosDaEntrada(e: api.FeedEntrada, buscaAtiva: string, leiturasPorCategoria: number): string[] {
  const m: string[] = [];
  if (e.urgente) m.push("Marcado como urgente pela redação.");
  if (e.numero_fontes >= 3) m.push(`Confirmado por ${e.numero_fontes} fontes diferentes.`);
  if (buscaAtiva) m.push(`Corresponde à sua busca por "${buscaAtiva}".`);
  if (leiturasPorCategoria >= 2 && e.categoria) m.push(`Você já leu ${leiturasPorCategoria} notícias de ${e.categoria} nesta sessão.`);
  if (m.length===0) m.push("Publicado recentemente no feed geral.");
  return m;
}
function agruparPorCategoria(itens: api.FeedEntrada[]): Record<string, api.FeedEntrada[]> {
  const g: Record<string, api.FeedEntrada[]> = {};
  for (const it of itens) { const cat=(it.categoria||"geral").toLowerCase(); if(!g[cat]) g[cat]=[]; g[cat].push(it); }
  return g;
}

function PaginaFeedInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [itens, setItens] = useState<api.FeedEntrada[]>([]);
  const [exibirPublicidade, setExibirPublicidade] = useState(true);
  const [categoria, setCategoria] = useState(()=>searchParams.get("categoria")||"");
  const [buscaDigitada, setBuscaDigitada] = useState(()=>searchParams.get("busca")||"");
  const [buscaAtiva, setBuscaAtiva] = useState(()=>searchParams.get("busca")||"");
  const [pagina, setPagina] = useState(1);
  const [temMais, setTemMais] = useState(false);
  const [carregandoInicial, setCarregandoInicial] = useState(true);
  const [carregandoMais, setCarregandoMais] = useState(false);
  const [erro, setErro] = useState<string|null>(null);
  const [categoriaPreferida, setCategoriaPreferida] = useState<intencao.CategoriaPreferida|null>(null);
  const [sugestaoDispensada, setSugestaoDispensada] = useState(false);
  const [novidadeDisponivel, setNovidadeDisponivel] = useState<api.FeedResposta|null>(null);
  const [verSalvos, setVerSalvos] = useState(false);
  const [salvos, setSalvos] = useState<api.FeedEntrada[]>([]);
  const [emailNewsletter, setEmailNewsletter] = useState("");
  const [msgNewsletter, setMsgNewsletter] = useState<string|null>(null);
  const [carregandoNewsletter, setCarregandoNewsletter] = useState(false);
  const buscaId = useId();
  const sentinelaRef = useRef<HTMLDivElement|null>(null);
  const primeiraChaveRef = useRef<string|null>(null);

  useEffect(()=>{ const cat=searchParams.get("categoria")||""; const b=searchParams.get("busca")||""; if(cat!==categoria) setCategoria(cat); if(b!==buscaAtiva){ setBuscaDigitada(b); setBuscaAtiva(b);} },[searchParams]);
  useEffect(()=>{ const t=window.setTimeout(()=>{ const v=buscaDigitada.trim(); setBuscaAtiva((a)=>(a===v?a:v)); },ATRASO_BUSCA_MS); return ()=>window.clearTimeout(t); },[buscaDigitada]);
  useEffect(()=>{
    const p=new URLSearchParams(searchParams.toString()); let mudou=false;
    if(buscaAtiva){ if(p.get("busca")!==buscaAtiva){ p.set("busca",buscaAtiva); mudou=true; }} else if(p.has("busca")){ p.delete("busca"); mudou=true; }
    if(categoria){ if(p.get("categoria")!==categoria){ p.set("categoria",categoria); mudou=true; }} else if(p.has("categoria")){ p.delete("categoria"); mudou=true; }
    if(mudou){ const qs=p.toString(); router.replace(qs?`/?${qs}`:"/",{scroll:false}); }
  },[buscaAtiva,categoria]);

  useEffect(()=>{ setPagina(1); setItens([]); setNovidadeDisponivel(null); setSugestaoDispensada(false); },[categoria,buscaAtiva]);

  useEffect(()=>{
    let c=false; if(pagina===1) setCarregandoInicial(true); else setCarregandoMais(true); setErro(null);
    api.obterFeed({ categoria:categoria||undefined, busca:buscaAtiva||undefined, page:pagina }).then((r)=>{
      if(c) return; setItens((a)=>(pagina===1? r.results : [...a,...r.results])); setExibirPublicidade(r.exibir_publicidade); setTemMais(Boolean(r.next));
    }).catch((e:unknown)=>{ if(c) return; setErro(e instanceof api.ApiError? e.message : "Não foi possível carregar o feed."); }).finally(()=>{ if(c) return; setCarregandoInicial(false); setCarregandoMais(false); });
    return ()=>{ c=true; };
  },[categoria,buscaAtiva,pagina]);

  useEffect(()=>{ primeiraChaveRef.current=itens[0]?chaveDaEntrada(itens[0]):null; },[itens]);
  useEffect(()=>{ setCategoriaPreferida(intencao.obterCategoriaPreferida()); },[itens]);
  useEffect(()=>{
    if(!temMais||carregandoMais||carregandoInicial) return;
    const el=sentinelaRef.current; if(!el) return;
    const obs=new IntersectionObserver((entries)=>{ if(entries[0]?.isIntersecting) setPagina((p)=>p+1); },{rootMargin:"400px"});
    obs.observe(el); return ()=>obs.disconnect();
  },[temMais,carregandoMais,carregandoInicial,itens.length]);
  useEffect(()=>{
    const verificar=()=>{ if(document.hidden) return; api.obterFeed({ categoria:categoria||undefined, busca:buscaAtiva||undefined, page:1 }).then((r)=>{ const chaveNova=r.results[0]?chaveDaEntrada(r.results[0]):null; if(chaveNova && chaveNova!==primeiraChaveRef.current) setNovidadeDisponivel(r); }).catch(()=>{}); };
    const id=window.setInterval(verificar, INTERVALO_VERIFICACAO_NOVIDADES_MS); return ()=>window.clearInterval(id);
  },[categoria,buscaAtiva]);
  useEffect(()=>{ if(verSalvos) setSalvos(bookmarks.obterSalvos()); },[verSalvos]);

  function aoSubmeterBusca(e: FormEvent){ e.preventDefault(); setBuscaAtiva(buscaDigitada.trim()); }
  function aplicarNovidade(){ if(!novidadeDisponivel) return; setItens(novidadeDisponivel.results); setExibirPublicidade(novidadeDisponivel.exibir_publicidade); setTemMais(Boolean(novidadeDisponivel.next)); setPagina(1); setNovidadeDisponivel(null); window.scrollTo({top:0,behavior:"smooth"}); }
  function aplicarSugestaoDeCategoria(){ if(!categoriaPreferida) return; setCategoria(categoriaPreferida.categoria); setSugestaoDispensada(true); }
  const mostrarSugestao=!sugestaoDispensada && !categoria && !buscaAtiva && categoriaPreferida!==null;
  const modoMosaico=!categoria && !buscaAtiva && !verSalvos;
  const itemHero=modoMosaico && itens.length>0 ? itens[0] : null;
  const itensMosaicoLateral=modoMosaico? itens.slice(1,4):[];
  const itensAposMosaico=modoMosaico? itens.slice(4):itens;
  const grupos=modoMosaico? agruparPorCategoria(itensAposMosaico):{};
  const categoriasComConteudo=Object.keys(grupos).slice(0,3);

  async function onNewsletter(e: FormEvent){
    e.preventDefault();
    const email=emailNewsletter.trim();
    if(!email) return;
    if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){ setMsgNewsletter("Digite um e-mail válido."); return; }
    setCarregandoNewsletter(true);
    try {
      const r=await api.assinarNewsletterPublica(email, categoria||"geral");
      setMsgNewsletter(r.detail || "Inscrição confirmada — obrigado!");
      setEmailNewsletter("");
    } catch (err:unknown) {
      setMsgNewsletter(err instanceof api.ApiError ? err.message : "Não foi possível inscrever. Tente novamente.");
    } finally { setCarregandoNewsletter(false); setTimeout(()=>setMsgNewsletter(null),5000); }
  }

  if(verSalvos){
    return (
      <div>
        <div className="controles-salvos"><button type="button" className="botao botao-secundario" onClick={()=>setVerSalvos(false)}>← Voltar ao feed</button></div>
        {salvos.length===0? <p className="texto-suave">Nenhuma notícia salva ainda.</p> : (
          <div className="grade-noticias">{salvos.map((entrada)=>{
            const v=obterVisualCategoria(entrada.categoria);
            return (
              <Link key={chaveDaEntrada(entrada)} href={`/noticia/${entrada.tipo}/${entrada.id}`} className="card-noticia" style={{["--acento" as string]:v.cor}}>
                <div className="card-noticia-imagem" style={{["--gradiente" as string]:v.gradiente}}><span className="mosaico-badge">{entrada.categoria||"geral"}</span></div>
                <div className="card-noticia-corpo"><h2 className="card-noticia-titulo">{entrada.titulo}</h2><p className="card-noticia-resumo">{entrada.resumo}</p><div className="card-noticia-meta"><span>{formatarData(entrada.timestamp)}</span><span>{entrada.numero_fontes} fontes</span></div><BotaoSalvar entrada={entrada}/></div>
              </Link>
            );})}</div>
        )}
      </div>
    );
  }

  return (
    <div>
      {exibirPublicidade && <div className="faixa-publicidade">Espaço publicitário — assine o <Link href="/planos">Premium</Link> para navegar sem anúncios.</div>}
      {modoMosaico && <TickerUrgente />}
      {novidadeDisponivel && <div className="banner-atualizacao"><button type="button" onClick={aplicarNovidade}>↑ Novas notícias disponíveis — atualizar</button></div>}
      {mostrarSugestao && categoriaPreferida && (
        <div className="sugestao-adaptativa" role="status">
          <span>Notamos que você tem lido bastante sobre <strong>{categoriaPreferida.categoria}</strong>. Quer filtrar o feed por esse tema?</span>
          <div className="sugestao-adaptativa-acoes">
            <button type="button" className="botao" onClick={aplicarSugestaoDeCategoria}>Filtrar por {categoriaPreferida.categoria}</button>
            <button type="button" className="botao botao-secundario" onClick={()=>setSugestaoDispensada(true)}>Agora não</button>
          </div>
        </div>
      )}

      <form onSubmit={aoSubmeterBusca} className="controles-feed" style={{display: modoMosaico? "none":"flex"}}>
        <div className="campo-controle"><label htmlFor={buscaId}>Buscar</label><input id={buscaId} type="search" placeholder="Palavra-chave" value={buscaDigitada} onChange={(e)=>setBuscaDigitada(e.target.value)} style={{maxWidth:280, width:"100%"}}/></div>
        <button type="submit" className="botao">Buscar</button>
        <button type="button" className="botao botao-secundario" onClick={()=>setVerSalvos(true)}>★ Salvos ({bookmarks.obterSalvos().length})</button>
      </form>

      <div className="filtro-categorias" role="group" aria-label="Filtrar por categoria">
        <Chip selecionado={categoria===""} aoClicar={()=>setCategoria("")}>Todas</Chip>
        {CATEGORIAS_REFERENCIA.map((c)=>{ const v=obterVisualCategoria(c); return (<Chip key={c} selecionado={categoria===c} aoClicar={()=>setCategoria(categoria===c?"":c)}><span className="cartao-emoji" aria-hidden="true">{v.emoji}</span>{c}</Chip>); })}
      </div>

      {carregandoInicial && <div className="grade-noticias" aria-hidden="true">{Array.from({length:6}).map((_,i)=><CartaoEsqueleto key={i}/>)}</div>}

      {!carregandoInicial && modoMosaico && itemHero && (
        <div className="mosaico">
          <Link href={`/noticia/${itemHero.tipo}/${itemHero.id}`} className="mosaico-destaque" style={{["--gradiente" as string]:obterVisualCategoria(itemHero.categoria).gradiente}}>
            <span className={`mosaico-badge ${itemHero.urgente?"mosaico-badge--urgente":""}`}>{itemHero.urgente?"Urgente":itemHero.categoria||"destaque"}</span>
            <h2 className="mosaico-titulo">{itemHero.titulo}</h2>
            <p className="mosaico-resumo">{itemHero.resumo}</p>
            <div className="mosaico-meta"><span>{formatarData(itemHero.timestamp)}</span><span>{itemHero.numero_fontes} fontes</span></div>
          </Link>
          <div className="mosaico-lateral">
            {itensMosaicoLateral.map((entrada)=>{ const v=obterVisualCategoria(entrada.categoria); return (
              <Link key={chaveDaEntrada(entrada)} href={`/noticia/${entrada.tipo}/${entrada.id}`} className="card-mosaico-sec" style={{["--gradiente" as string]:v.gradiente}}>
                <span className={`mosaico-badge ${entrada.urgente?"mosaico-badge--urgente":""}`}>{entrada.categoria||"geral"}</span>
                <h3 className="card-mosaico-sec-titulo">{entrada.titulo}</h3>
              </Link>
            );})}
            {itensMosaicoLateral.length<3 && Array.from({length:3-itensMosaicoLateral.length}).map((_,i)=><div key={`ph-${i}`} className="card-mosaico-sec" style={{background:"var(--cor-skeleton-base)"}}><span className="texto-suave" style={{color:"#fff",position:"relative",zIndex:1}}>Em breve</span></div>)}
          </div>
        </div>
      )}

      <div aria-live="polite">
        {erro && <p className="mensagem-erro">{erro}</p>}
        {!carregandoInicial && !erro && itens.length===0 && <p className="texto-suave">Nenhuma notícia encontrada com esses filtros.</p>}
      </div>

      {!carregandoInicial && (
        <div className={modoMosaico?"portal-layout":""}>
          <div>
            {modoMosaico ? (
              <>
                {categoriasComConteudo.map((cat)=>(
                  <BlocoEditoria key={cat} categoria={cat} itens={grupos[cat]} onVerTodas={()=>setCategoria(cat)} />
                ))}
                <section className="secao-bloco">
                  <div className="secao-cabecalho"><h2 className="secao-titulo">Últimas notícias</h2></div>
                  {itensAposMosaico.length===0? <p className="texto-suave">Mais notícias aparecerão aqui.</p> : (
                    <div className="lista-compacta">
                      {itensAposMosaico.slice(0,12).map((entrada)=>{ const v=obterVisualCategoria(entrada.categoria); return (
                        <Link key={chaveDaEntrada(entrada)} href={`/noticia/${entrada.tipo}/${entrada.id}`} className="item-compacto">
                          <div className="item-compacto-thumb" style={{background:v.gradiente}}/>
                          <div><p className="item-compacto-titulo">{entrada.titulo}</p><div className="item-compacto-meta"><Badge variante={entrada.urgente?"erro":"neutro"}>{entrada.urgente?"Urgente":entrada.categoria||"geral"}</Badge><span>{formatarData(entrada.timestamp)}</span></div></div>
                        </Link>
                      );})}
                    </div>
                  )}
                </section>
              </>
            ) : (
              itensAposMosaico.length>0 && (
                <div className="grade-noticias">
                  {itensAposMosaico.map((entrada)=>{ const v=obterVisualCategoria(entrada.categoria); const motivos=motivosDaEntrada(entrada,buscaAtiva,intencao.obterLeiturasDaCategoria(entrada.categoria)); return (
                    <article key={chaveDaEntrada(entrada)} className="card-noticia" style={{["--acento" as string]:v.cor}}>
                      <Link href={`/noticia/${entrada.tipo}/${entrada.id}`} className="card-noticia-imagem" style={{["--gradiente" as string]:v.gradiente, textDecoration:"none"}}><span className="mosaico-badge" style={{background:v.cor}}>{entrada.categoria||"geral"}</span></Link>
                      <div className="card-noticia-corpo"><Link href={`/noticia/${entrada.tipo}/${entrada.id}`} style={{textDecoration:"none",color:"inherit"}}><h3 className="card-noticia-titulo">{entrada.titulo}</h3></Link><p className="card-noticia-resumo">{entrada.resumo}</p><div className="card-noticia-meta"><span>{formatarData(entrada.timestamp)}</span><span>{entrada.numero_fontes} fontes</span></div><div className="cartao-acoes"><PorQueEstouVendoIsso motivos={motivos}/><BotaoSalvar entrada={entrada}/></div></div>
                    </article>
                  );})}
                </div>
              )
            )}
          </div>
          {modoMosaico && (
            <aside className="sidebar">
              <MaisLidas limite={5} />
              <div className="newsletter-box">
                <h3>Receba as principais</h3>
                <p>As manchetes do dia no seu e-mail — real, via lista de espera.</p>
                <form onSubmit={onNewsletter} style={{display:"flex", gap:8, flexWrap:"wrap"}}>
                  <input type="email" placeholder="Seu e-mail" value={emailNewsletter} onChange={(e)=>setEmailNewsletter(e.target.value)} required style={{flex:"1 1 160px", minWidth:0}} />
                  <button type="submit" className="botao" disabled={carregandoNewsletter}>{carregandoNewsletter?"Enviando…":"Inscrever"}</button>
                </form>
                {msgNewsletter && <p style={{marginTop:8, fontSize:"0.8rem", color: msgNewsletter.includes("válido")||msgNewsletter.includes("Não foi")?"#ffb4a8":"#4fd17a"}}>{msgNewsletter}</p>}
              </div>
              <div className="bloco-sidebar">
                <div className="bloco-sidebar-cabecalho"><h2 className="bloco-sidebar-titulo">Salvos</h2><button type="button" className="botao botao-secundario" style={{fontSize:"0.75rem", padding:"0.25rem 0.6rem"}} onClick={()=>setVerSalvos(true)}>Ver todos</button></div>
                <div style={{padding:"var(--espaco-3) var(--espaco-4)"}}>
                  {bookmarks.obterSalvos().length===0? <p className="texto-suave" style={{margin:0}}>Salve notícias para ler depois.</p> : (
                    <ul style={{margin:0,paddingLeft:"1.1rem",fontSize:"0.85rem",display:"flex",flexDirection:"column",gap:6}}>
                      {bookmarks.obterSalvos().slice(0,3).map((s)=><li key={`${s.tipo}-${s.id}`}><Link href={`/noticia/${s.tipo}/${s.id}`}>{s.titulo}</Link></li>)}
                    </ul>
                  )}
                </div>
              </div>
              <div className="bloco-sidebar" style={{padding:"var(--espaco-4)", textAlign:"center", background:"var(--cor-fundo-card)"}}>
                <p className="texto-suave" style={{margin:"0 0 8px"}}>Anúncio</p>
                <div style={{height:180, background:"var(--cor-skeleton-base)", borderRadius:8, display:"flex", alignItems:"center", justifyContent:"center", color:"var(--cor-texto-suave)", fontSize:"0.8rem"}}>Espaço publicitário</div>
                <p style={{marginTop:8}}><Link href="/planos" style={{fontSize:"0.8rem"}}>Remover anúncios com Premium →</Link></p>
              </div>
            </aside>
          )}
        </div>
      )}
      {!carregandoInicial && temMais && (
        <div className="sentinela-carregamento" ref={sentinelaRef}>
          <button type="button" className="botao botao-secundario" onClick={()=>setPagina((p)=>p+1)} disabled={carregandoMais}>{carregandoMais?"Carregando…":"Carregar mais notícias"}</button>
        </div>
      )}
    </div>
  );
}

export default function PaginaFeed(){ return (<Suspense fallback={null}><PaginaFeedInner/></Suspense>); }
