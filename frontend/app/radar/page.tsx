"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

export default function PaginaRadar() {
  const { token, usuario } = useAuth();

  const [pais, setPais] = useState("");
  const [estado, setEstado] = useState("");
  const [cidade, setCidade] = useState("");
  const [tendencias, setTendencias] = useState<api.RadarTendencias | null>(null);
  const [evolucao, setEvolucao] = useState<api.RadarEvolucao | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [erroEvolucao, setErroEvolucao] = useState<string | null>(null);
  const [salvo, setSalvo] = useState(false);

  function buscarTendencias(filtros: { pais?: string; estado?: string; cidade?: string }) {
    setCarregando(true);
    setErro(null);
    api
      .obterTendenciasRadar(filtros)
      .then(setTendencias)
      .catch((e: unknown) => setErro(e instanceof api.ApiError ? e.message : "Não foi possível carregar o radar."))
      .finally(() => setCarregando(false));
  }

  useEffect(() => {
    buscarTendencias({});
  }, []);

  function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setSalvo(false);
    setEvolucao(null);
    buscarTendencias({ pais, estado, cidade });
  }

  async function verEvolucao(categoria: string) {
    if (!token) return;
    setErroEvolucao(null);
    try {
      const dados = await api.obterEvolucaoRadar(token, { categoria, pais, estado, cidade });
      setEvolucao(dados);
    } catch (e) {
      setErroEvolucao(
        e instanceof api.ApiError ? e.message : "Não foi possível carregar a evolução."
      );
    }
  }

  async function salvarLocalidadeAtual() {
    if (!token) return;
    try {
      await api.salvarLocalidade(token, { pais, estado, cidade });
      setSalvo(true);
    } catch {
      // falha ao salvar não deve travar a navegação do radar
    }
  }

  return (
    <div>
      <h1>Radar de Tendências</h1>

      <form onSubmit={aoSubmeter} className="controles-feed">
        <input type="text" placeholder="País" value={pais} onChange={(e) => setPais(e.target.value)} />
        <input type="text" placeholder="Estado" value={estado} onChange={(e) => setEstado(e.target.value)} />
        <input type="text" placeholder="Cidade" value={cidade} onChange={(e) => setCidade(e.target.value)} />
        <button type="submit" className="botao">
          Filtrar
        </button>
        {token && (
          <button type="button" className="botao botao-secundario" onClick={salvarLocalidadeAtual}>
            {salvo ? "Localidade salva ✓" : "Salvar localidade"}
          </button>
        )}
      </form>

      {erro && <p className="mensagem-erro">{erro}</p>}
      {carregando && <p className="texto-suave">Carregando...</p>}

      {tendencias && (
        <>
          <p className="texto-suave" style={{ fontStyle: "italic" }}>
            {tendencias.aviso_metodologia}
          </p>
          {tendencias.assuntos_em_alta.length === 0 && (
            <p className="texto-suave">Nenhum assunto em alta neste recorte ainda.</p>
          )}
          {tendencias.assuntos_em_alta.map((assunto) => (
            <div className="cartao" key={assunto.categoria}>
              <div className="cartao-meta">
                <span className="badge-categoria">{assunto.categoria}</span>
                <span>{assunto.numero_noticias} notícia(s)</span>
                <span>{assunto.numero_fontes} fonte(s)</span>
              </div>
              {assunto.cluster_id ? (
                <Link href={`/noticia/cluster/${assunto.cluster_id}`}>Ver acontecimento agrupado</Link>
              ) : assunto.item_id ? (
                <Link href={`/noticia/item/${assunto.item_id}`}>Ver notícia</Link>
              ) : null}
              {usuario?.papel === "premium" ? (
                <button
                  type="button"
                  className="botao botao-secundario"
                  onClick={() => verEvolucao(assunto.categoria)}
                >
                  Ver evolução
                </button>
              ) : (
                <p className="texto-suave">Evolução ao longo do tempo é um recurso Premium.</p>
              )}
            </div>
          ))}
        </>
      )}

      {erroEvolucao && <p className="mensagem-erro">{erroEvolucao}</p>}
      {evolucao && (
        <div className="cartao">
          <strong>Evolução — {evolucao.categoria}</strong>
          <ul>
            {evolucao.serie.map((ponto) => (
              <li key={ponto.dia}>
                {ponto.dia}: {ponto.numero_noticias} notícia(s)
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
