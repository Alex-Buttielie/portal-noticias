"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import * as intencao from "@/lib/intent";
import * as bookmarks from "@/lib/bookmarks";
import { obterVisualCategoria } from "@/lib/categoryVisuals";
import CartaoEsqueleto from "@/components/CartaoEsqueleto";
import PorQueEstouVendoIsso from "@/components/PorQueEstouVendoIsso";
import BotaoSalvar from "@/components/BotaoSalvar";
import Chip from "@/components/Chip";
import Badge from "@/components/Badge";

// Lista de referência (ARCHITECTURE.md / task-plan.md do backend feed/) —
// não é uma enumeração travada: o filtro aceita qualquer valor presente nos
// dados, esta lista é só para popular o seletor com opções conhecidas.
const CATEGORIAS_REFERENCIA = [
  "política",
  "economia",
  "esportes",
  "tecnologia",
  "saúde",
  "cultura",
  "cidades",
  "mundo",
  "ciência",
];

const ATRASO_BUSCA_MS = 400;
const INTERVALO_VERIFICACAO_NOVIDADES_MS = 60000;

function formatarData(timestamp: string): string {
  try {
    return new Date(timestamp).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return timestamp;
  }
}

function chaveDaEntrada(entrada: api.FeedEntrada): string {
  return `${entrada.tipo}-${entrada.id}`;
}

function motivosDaEntrada(
  entrada: api.FeedEntrada,
  buscaAtiva: string,
  leiturasPorCategoria: number
): string[] {
  const motivos: string[] = [];
  if (entrada.urgente) {
    motivos.push("Marcado como urgente pela redação.");
  }
  if (entrada.numero_fontes >= 3) {
    motivos.push(`Confirmado por ${entrada.numero_fontes} fontes diferentes.`);
  }
  if (buscaAtiva) {
    motivos.push(`Corresponde à sua busca por "${buscaAtiva}".`);
  }
  if (leiturasPorCategoria >= 2 && entrada.categoria) {
    motivos.push(`Você já leu ${leiturasPorCategoria} notícias de ${entrada.categoria} nesta sessão.`);
  }
  if (motivos.length === 0) {
    motivos.push("Publicado recentemente no feed geral.");
  }
  return motivos;
}

export default function PaginaFeed() {
  const [itens, setItens] = useState<api.FeedEntrada[]>([]);
  const [exibirPublicidade, setExibirPublicidade] = useState(true);
  const [categoria, setCategoria] = useState("");
  const [buscaDigitada, setBuscaDigitada] = useState("");
  const [buscaAtiva, setBuscaAtiva] = useState("");
  const [pagina, setPagina] = useState(1);
  const [temMais, setTemMais] = useState(false);
  const [carregandoInicial, setCarregandoInicial] = useState(true);
  const [carregandoMais, setCarregandoMais] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [categoriaPreferida, setCategoriaPreferida] = useState<intencao.CategoriaPreferida | null>(null);
  const [sugestaoDispensada, setSugestaoDispensada] = useState(false);
  const [novidadeDisponivel, setNovidadeDisponivel] = useState<api.FeedResposta | null>(null);
  const [verSalvos, setVerSalvos] = useState(false);
  const [salvos, setSalvos] = useState<api.FeedEntrada[]>([]);
  const buscaId = useId();
  const sentinelaRef = useRef<HTMLDivElement | null>(null);
  const primeiraChaveRef = useRef<string | null>(null);

  // Busca ao vivo: reflete a digitação após uma pausa curta, sem esperar um
  // clique em "Buscar" — mantém a interface respondendo enquanto o usuário
  // ainda está formulando a consulta.
  useEffect(() => {
    const temporizador = window.setTimeout(() => {
      const valor = buscaDigitada.trim();
      setBuscaAtiva((atual) => (atual === valor ? atual : valor));
    }, ATRASO_BUSCA_MS);
    return () => window.clearTimeout(temporizador);
  }, [buscaDigitada]);

  // Qualquer mudança de filtro reinicia a listagem do zero (rolagem
  // infinita recomeça na página 1).
  useEffect(() => {
    setPagina(1);
    setItens([]);
    setNovidadeDisponivel(null);
    setSugestaoDispensada(false);
  }, [categoria, buscaAtiva]);

  useEffect(() => {
    let cancelado = false;
    if (pagina === 1) setCarregandoInicial(true);
    else setCarregandoMais(true);
    setErro(null);

    api
      .obterFeed({
        categoria: categoria || undefined,
        busca: buscaAtiva || undefined,
        page: pagina,
      })
      .then((resposta) => {
        if (cancelado) return;
        setItens((atual) => (pagina === 1 ? resposta.results : [...atual, ...resposta.results]));
        setExibirPublicidade(resposta.exibir_publicidade);
        setTemMais(Boolean(resposta.next));
      })
      .catch((e: unknown) => {
        if (cancelado) return;
        setErro(e instanceof api.ApiError ? e.message : "Não foi possível carregar o feed.");
      })
      .finally(() => {
        if (cancelado) return;
        setCarregandoInicial(false);
        setCarregandoMais(false);
      });

    return () => {
      cancelado = true;
    };
  }, [categoria, buscaAtiva, pagina]);

  useEffect(() => {
    primeiraChaveRef.current = itens[0] ? chaveDaEntrada(itens[0]) : null;
  }, [itens]);

  useEffect(() => {
    setCategoriaPreferida(intencao.obterCategoriaPreferida());
  }, [itens]);

  // Rolagem infinita: carrega a próxima página automaticamente quando o
  // marcador ao final da grade entra na tela.
  useEffect(() => {
    if (!temMais || carregandoMais || carregandoInicial) return;
    const elemento = sentinelaRef.current;
    if (!elemento) return;

    const observador = new IntersectionObserver(
      (entradasObservadas) => {
        if (entradasObservadas[0]?.isIntersecting) {
          setPagina((p) => p + 1);
        }
      },
      { rootMargin: "400px" }
    );
    observador.observe(elemento);
    return () => observador.disconnect();
  }, [temMais, carregandoMais, carregandoInicial, itens.length]);

  // Feed vivo: verifica periodicamente se surgiu conteúdo novo no topo e
  // avisa por um banner discreto — nunca insere nada sem o usuário pedir,
  // para não empurrar o que ele já está lendo. Pausa quando a aba não está
  // visível (menos chamadas de rede = design mais sustentável).
  useEffect(() => {
    const verificar = () => {
      if (document.hidden) return;
      api
        .obterFeed({ categoria: categoria || undefined, busca: buscaAtiva || undefined, page: 1 })
        .then((resposta) => {
          const chaveNova = resposta.results[0] ? chaveDaEntrada(resposta.results[0]) : null;
          if (chaveNova && chaveNova !== primeiraChaveRef.current) {
            setNovidadeDisponivel(resposta);
          }
        })
        .catch(() => {
          // verificação em segundo plano — falha aqui não deve incomodar o usuário
        });
    };
    const intervalo = window.setInterval(verificar, INTERVALO_VERIFICACAO_NOVIDADES_MS);
    return () => window.clearInterval(intervalo);
  }, [categoria, buscaAtiva]);

  // "Ver salvos" é inteiramente local — lê direto do localStorage, sem
  // chamar a API, então abre na hora e funciona com qualquer filtro que
  // estivesse ativo no feed.
  useEffect(() => {
    if (verSalvos) setSalvos(bookmarks.obterSalvos());
  }, [verSalvos]);

  function aoSubmeterBusca(evento: FormEvent) {
    evento.preventDefault();
    setBuscaAtiva(buscaDigitada.trim());
  }

  function aplicarNovidade() {
    if (!novidadeDisponivel) return;
    setItens(novidadeDisponivel.results);
    setExibirPublicidade(novidadeDisponivel.exibir_publicidade);
    setTemMais(Boolean(novidadeDisponivel.next));
    setPagina(1);
    setNovidadeDisponivel(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function aplicarSugestaoDeCategoria() {
    if (!categoriaPreferida) return;
    setCategoria(categoriaPreferida.categoria);
    setSugestaoDispensada(true);
  }

  const mostrarSugestao =
    !sugestaoDispensada && !categoria && !buscaAtiva && categoriaPreferida !== null;

  // Destaque editorial: só faz sentido sem filtro/busca ativos (senão o
  // "destaque" seria só o primeiro resultado filtrado, confuso).
  const mostrarHero = !categoria && !buscaAtiva && itens.length > 0;
  const itemHero = mostrarHero ? itens[0] : null;
  const itensGrade = mostrarHero ? itens.slice(1) : itens;

  return (
    <div>
      <h1>Feed de notícias</h1>

      <div className="controles-salvos">
        <button
          type="button"
          className="botao botao-secundario"
          onClick={() => setVerSalvos((v) => !v)}
        >
          {verSalvos ? "← Voltar ao feed" : `★ Ver salvos (${bookmarks.obterSalvos().length})`}
        </button>
      </div>

      {verSalvos ? (
        <div>
          {salvos.length === 0 ? (
            <p className="texto-suave">
              Nenhuma notícia salva ainda. Clique em "Salvar para depois" em qualquer notícia do
              feed.
            </p>
          ) : (
            <div className="grade-cartoes">
              {salvos.map((entrada) => (
                <Link
                  key={chaveDaEntrada(entrada)}
                  href={`/noticia/${entrada.tipo}/${entrada.id}`}
                  style={{ textDecoration: "none", color: "inherit" }}
                >
                  <article className="cartao">
                    <div className="cartao-meta">
                      {entrada.urgente && <span className="badge-urgente">Urgente</span>}
                      {entrada.categoria && (
                        <span className="badge-categoria">{entrada.categoria}</span>
                      )}
                      <span>{formatarData(entrada.timestamp)}</span>
                    </div>
                    <h2 className="cartao-titulo">{entrada.titulo}</h2>
                    <p className="texto-suave">{entrada.resumo}</p>
                    <div className="cartao-acoes">
                      <BotaoSalvar entrada={entrada} />
                    </div>
                  </article>
                </Link>
              ))}
            </div>
          )}
        </div>
      ) : (
        <>
      {exibirPublicidade && (
        <div className="faixa-publicidade">
          Espaço publicitário — assine o <Link href="/planos">Premium</Link> para navegar
          sem anúncios.
        </div>
      )}

      {novidadeDisponivel && (
        <div className="banner-atualizacao">
          <button type="button" onClick={aplicarNovidade}>
            ↑ Novas notícias disponíveis — atualizar
          </button>
        </div>
      )}

      {mostrarSugestao && categoriaPreferida && (
        <div className="sugestao-adaptativa" role="status">
          <span>
            Notamos que você tem lido bastante sobre <strong>{categoriaPreferida.categoria}</strong>{" "}
            nesta sessão. Quer filtrar o feed por esse tema?
          </span>
          <div className="sugestao-adaptativa-acoes">
            <button type="button" className="botao" onClick={aplicarSugestaoDeCategoria}>
              Filtrar por {categoriaPreferida.categoria}
            </button>
            <button
              type="button"
              className="botao botao-secundario"
              onClick={() => setSugestaoDispensada(true)}
            >
              Agora não
            </button>
          </div>
        </div>
      )}

      <form onSubmit={aoSubmeterBusca} className="controles-feed">
        <div className="campo-controle">
          <label htmlFor={buscaId}>Buscar</label>
          <input
            id={buscaId}
            type="search"
            placeholder="Palavra-chave"
            value={buscaDigitada}
            onChange={(e) => setBuscaDigitada(e.target.value)}
            style={{ maxWidth: 280 }}
          />
        </div>
        <button type="submit" className="botao">
          Buscar
        </button>
      </form>

      <div className="filtro-categorias" role="group" aria-label="Filtrar por categoria">
        <Chip selecionado={categoria === ""} aoClicar={() => setCategoria("")}>
          Todas
        </Chip>
        {CATEGORIAS_REFERENCIA.map((c) => {
          const visual = obterVisualCategoria(c);
          return (
            <Chip key={c} selecionado={categoria === c} aoClicar={() => setCategoria(categoria === c ? "" : c)}>
              <span className="cartao-emoji" aria-hidden="true">
                {visual.emoji}
              </span>
              {c}
            </Chip>
          );
        })}
      </div>

      {mostrarHero && itemHero && (
        <Link
          href={`/noticia/${itemHero.tipo}/${itemHero.id}`}
          style={{ textDecoration: "none", color: "inherit" }}
        >
          <article
            className="cartao-hero"
            style={{ ["--acento" as string]: obterVisualCategoria(itemHero.categoria).cor }}
          >
            <div className="cartao-hero-rotulo">
              <span aria-hidden="true">{obterVisualCategoria(itemHero.categoria).emoji}</span>
              {itemHero.urgente ? "Manchete urgente" : "Destaque de agora"}
            </div>
            <h2 className="cartao-hero-titulo">{itemHero.titulo}</h2>
            <p className="cartao-hero-resumo">{itemHero.resumo}</p>
            <div className="cartao-meta">
              {itemHero.urgente && <Badge variante="erro">Urgente</Badge>}
              {itemHero.categoria && <Badge variante="neutro">{itemHero.categoria}</Badge>}
              <span>{formatarData(itemHero.timestamp)}</span>
              <span>
                {itemHero.numero_fontes} fonte{itemHero.numero_fontes === 1 ? "" : "s"}
              </span>
            </div>
          </article>
        </Link>
      )}

      <div aria-live="polite">
        {erro && <p className="mensagem-erro">{erro}</p>}
        {!carregandoInicial && !erro && itens.length === 0 && (
          <p className="texto-suave">Nenhuma notícia encontrada com esses filtros.</p>
        )}
      </div>

      {carregandoInicial && (
        <div className="grade-cartoes" aria-hidden="true">
          {Array.from({ length: 6 }).map((_, indice) => (
            <CartaoEsqueleto key={indice} />
          ))}
        </div>
      )}

      {!carregandoInicial && itensGrade.length > 0 && (
        <div className="grade-cartoes">
          {itensGrade.map((entrada) => {
            const leiturasCategoria = intencao.obterLeiturasDaCategoria(entrada.categoria);
            const motivos = motivosDaEntrada(entrada, buscaAtiva, leiturasCategoria);
            const visual = obterVisualCategoria(entrada.categoria);
            return (
              <Link
                key={chaveDaEntrada(entrada)}
                href={`/noticia/${entrada.tipo}/${entrada.id}`}
                style={{ textDecoration: "none", color: "inherit" }}
              >
                <article
                  className="cartao cartao--organico cartao-acento"
                  style={{ ["--acento" as string]: visual.cor }}
                >
                  <div className="cartao-meta">
                    {entrada.urgente && <Badge variante="erro">Urgente</Badge>}
                    {entrada.categoria && (
                      <Badge variante="neutro">
                        <span className="cartao-emoji" aria-hidden="true">
                          {visual.emoji}
                        </span>
                        {entrada.categoria}
                      </Badge>
                    )}
                    <span>{formatarData(entrada.timestamp)}</span>
                    <span>
                      {entrada.numero_fontes} fonte{entrada.numero_fontes === 1 ? "" : "s"}
                    </span>
                  </div>
                  <h2 className="cartao-titulo">{entrada.titulo}</h2>
                  <p className="texto-suave">{entrada.resumo}</p>
                  <div className="cartao-acoes">
                    <PorQueEstouVendoIsso motivos={motivos} />
                    <BotaoSalvar entrada={entrada} />
                  </div>
                </article>
              </Link>
            );
          })}
        </div>
      )}

      {!carregandoInicial && temMais && (
        <div className="sentinela-carregamento" ref={sentinelaRef}>
          <button
            type="button"
            className="botao botao-secundario"
            onClick={() => setPagina((p) => p + 1)}
            disabled={carregandoMais}
          >
            {carregandoMais ? "Carregando..." : "Carregar mais notícias"}
          </button>
        </div>
      )}
      </>
      )}
    </div>
  );
}
