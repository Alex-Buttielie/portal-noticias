"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useEvolucaoRadar, useLocalidadesSalvas, useRemoverLocalidade, useSalvarLocalidade, useTendenciasRadar } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoTexto } from "@/components/ui/FormField";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";

export default function PaginaRadar() {
  const { token, usuario } = useAuth();
  const { notificar } = useToast();

  const [pais, setPais] = useState("");
  const [estado, setEstado] = useState("");
  const [cidade, setCidade] = useState("");
  const [filtros, setFiltros] = useState<{ pais?: string; estado?: string; cidade?: string }>({});
  const [salvo, setSalvo] = useState(false);

  const tendencias = useTendenciasRadar(filtros);
  const evolucaoMutacao = useEvolucaoRadar();
  const salvarMutacao = useSalvarLocalidade();
  const salvasQuery = useLocalidadesSalvas();
  const removerMutacao = useRemoverLocalidade();

  function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setSalvo(false);
    evolucaoMutacao.reset();
    setFiltros({ pais: pais || undefined, estado: estado || undefined, cidade: cidade || undefined });
  }

  async function salvarLocalidadeAtual() {
    if (!token) return;
    try {
      await salvarMutacao.mutateAsync({ pais: pais || undefined, estado: estado || undefined, cidade: cidade || undefined });
      setSalvo(true);
      notificar("Localidade salva.", "sucesso");
    } catch {
      // falha ao salvar não deve travar a navegação do radar
    }
  }

  async function removerLocalidadeSalva(local: { pais?: string; estado?: string; cidade?: string }) {
    if (!window.confirm("Remover esta localidade salva?")) return;
    try {
      await removerMutacao.mutateAsync(local);
    } catch {
      notificar("Não foi possível remover a localidade.", "erro");
    }
  }

  const dados = tendencias.data ?? null;
  const evolucao = evolucaoMutacao.data ?? null;
  const salvas = salvasQuery.data ?? [];

  return (
    <div>
      <h1>Radar de Tendências</h1>

      <form onSubmit={aoSubmeter} className="controles-feed">
        <CampoTexto id="radar-pais" rotulo="País" value={pais} onChange={(e) => setPais(e.target.value)} />
        <CampoTexto id="radar-estado" rotulo="Estado" value={estado} onChange={(e) => setEstado(e.target.value)} />
        <CampoTexto id="radar-cidade" rotulo="Cidade" value={cidade} onChange={(e) => setCidade(e.target.value)} />
        <Button type="submit">Filtrar</Button>
        {token && (
          <Button variante="secundaria" onClick={() => void salvarLocalidadeAtual()} carregando={salvarMutacao.isPending}>
            {salvo ? "Localidade salva ✓" : "Salvar localidade"}
          </Button>
        )}
      </form>

      {tendencias.isLoading && <SkeletonLista quantidade={3} />}
      {tendencias.isError && (
        <ErrorState
          mensagem="Não foi possível carregar o radar."
          aoTentarNovamente={() => void tendencias.refetch()}
        />
      )}

      {dados && (
        <>
          <p className="texto-suave" style={{ fontStyle: "italic" }}>
            {dados.aviso_metodologia}
          </p>
          {dados.assuntos_em_alta.length === 0 && (
            <EmptyState titulo="Sem assuntos em alta" descricao="Nenhum assunto em alta neste recorte ainda." />
          )}
          {dados.assuntos_em_alta.map((assunto) => (
            <div className="cartao" key={assunto.categoria}>
              <div className="cartao-meta">
                <Badge variante="neutro">{assunto.categoria}</Badge>
                <span>{assunto.numero_noticias} notícia(s)</span>
                <span>{assunto.numero_fontes} fonte(s)</span>
              </div>
              {assunto.cluster_id ? (
                <Link href={`/noticia/cluster/${assunto.cluster_id}`}>Ver acontecimento agrupado</Link>
              ) : assunto.item_id ? (
                <Link href={`/noticia/item/${assunto.item_id}`}>Ver notícia</Link>
              ) : null}
              {usuario?.papel === "premium" ? (
                <div style={{ marginTop: "0.5rem" }}>
                  <Button
                    variante="secundaria"
                    tamanho="pequeno"
                    carregando={evolucaoMutacao.isPending}
                    onClick={() =>
                      evolucaoMutacao.mutate({
                        categoria: assunto.categoria,
                        pais: pais || undefined,
                        estado: estado || undefined,
                        cidade: cidade || undefined,
                      })
                    }
                  >
                    Ver evolução
                  </Button>
                </div>
              ) : (
                <p className="texto-suave">Evolução ao longo do tempo é um recurso Premium.</p>
              )}
            </div>
          ))}
        </>
      )}

      {evolucaoMutacao.isError && (
        <ErrorState
          mensagem={
            evolucaoMutacao.error instanceof api.ApiError
              ? evolucaoMutacao.error.message
              : "Não foi possível carregar a evolução."
          }
        />
      )}
      {token && salvas.length > 0 && (
        <section aria-label="Localidades salvas" style={{ marginTop: "1.5rem" }}>
          <h2 style={{ fontSize: "1.1rem" }}>Localidades salvas</h2>
          <ul style={{ listStyle: "none", padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
            {salvas.map((loc, i) => {
              const rotulo = [loc.cidade, loc.estado, loc.pais].filter(Boolean).join(" · ") || "Localidade";
              return (
                <li key={`${loc.pais}-${loc.estado}-${loc.cidade}-${i}`} style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <Button
                    variante="fantasma"
                    tamanho="pequeno"
                    onClick={() => {
                      setPais(loc.pais);
                      setEstado(loc.estado);
                      setCidade(loc.cidade);
                      setFiltros({ pais: loc.pais || undefined, estado: loc.estado || undefined, cidade: loc.cidade || undefined });
                    }}
                  >
                    {rotulo}
                  </Button>
                  <Button
                    variante="fantasma"
                    tamanho="pequeno"
                    carregando={removerMutacao.isPending}
                    onClick={() => void removerLocalidadeSalva({ pais: loc.pais || undefined, estado: loc.estado || undefined, cidade: loc.cidade || undefined })}
                  >
                    Remover
                  </Button>
                </li>
              );
            })}
          </ul>
        </section>
      )}
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
