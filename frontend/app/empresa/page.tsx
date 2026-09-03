"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

const ROTULOS_TIPO: Record<api.TipoCriterioMonitoramento, string> = {
  empresa: "Empresa",
  concorrente: "Concorrente",
  setor: "Setor",
  palavra_chave: "Palavra-chave",
};

export default function PaginaEmpresa() {
  const router = useRouter();
  const { token, usuario, carregando: carregandoAuth } = useAuth();

  const [criterios, setCriterios] = useState<api.CriterioMonitoramento[]>([]);
  const [itensMonitorados, setItensMonitorados] = useState<
    Record<string, { criterio: { tipo: string; valor: string }; itens: api.ItemMonitorado[] }>
  >({});
  const [resumo, setResumo] = useState<api.ResumoExecutivo | null>(null);
  const [membros, setMembros] = useState<api.MembroOrganizacao[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const [tipoCriterio, setTipoCriterio] = useState<api.TipoCriterioMonitoramento>("palavra_chave");
  const [valorCriterio, setValorCriterio] = useState("");
  const [criandoCriterio, setCriandoCriterio] = useState(false);

  const [emailConvite, setEmailConvite] = useState("");
  const [convidando, setConvidando] = useState(false);
  const [erroConvite, setErroConvite] = useState<string | null>(null);

  function carregarTudo(t: string) {
    setCarregando(true);
    setErro(null);
    Promise.all([
      api.obterCriteriosB2B(t),
      api.obterItensMonitoradosB2B(t),
      api.obterResumoExecutivoB2B(t),
      api.obterMembrosB2B(t),
    ])
      .then(([c, itens, r, m]) => {
        setCriterios(c);
        setItensMonitorados(itens);
        setResumo(r);
        setMembros(m);
      })
      .catch((e: unknown) => {
        if (e instanceof api.ApiError && e.status === 403) {
          setErro("Sua conta não pertence a nenhuma organização corporativa.");
        } else {
          setErro("Não foi possível carregar o painel da empresa.");
        }
      })
      .finally(() => setCarregando(false));
  }

  useEffect(() => {
    if (carregandoAuth) return;
    if (!token) {
      router.push("/login");
      return;
    }
    carregarTudo(token);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, carregandoAuth, router]);

  async function aoCriarCriterio(evento: FormEvent) {
    evento.preventDefault();
    if (!token || !valorCriterio.trim()) return;
    setCriandoCriterio(true);
    try {
      await api.criarCriterioB2B(token, { tipo: tipoCriterio, valor: valorCriterio.trim() });
      setValorCriterio("");
      carregarTudo(token);
    } catch (e) {
      setErro(e instanceof api.ApiError ? e.message : "Não foi possível criar o critério.");
    } finally {
      setCriandoCriterio(false);
    }
  }

  async function aoConvidar(evento: FormEvent) {
    evento.preventDefault();
    if (!token || !emailConvite.trim()) return;
    setConvidando(true);
    setErroConvite(null);
    try {
      await api.convidarMembroB2B(token, emailConvite.trim());
      setEmailConvite("");
      carregarTudo(token);
    } catch (e) {
      setErroConvite(e instanceof api.ApiError ? e.message : "Não foi possível convidar este usuário.");
    } finally {
      setConvidando(false);
    }
  }

  async function aoRemoverMembro(email: string) {
    if (!token) return;
    const confirmado = window.confirm(`Remover ${email} da organização?`);
    if (!confirmado) return;
    try {
      await api.removerMembroB2B(token, email);
      carregarTudo(token);
    } catch (e) {
      setErro(e instanceof api.ApiError ? e.message : "Não foi possível remover este membro.");
    }
  }

  const souAdmin = membros.some(
    (m) => m.email === usuario?.email && m.papel_na_organizacao === "admin_organizacao"
  );

  if (carregandoAuth || carregando) return <p className="texto-suave">Carregando...</p>;

  return (
    <div>
      <h1>Painel da empresa</h1>
      {erro && <p className="mensagem-erro">{erro}</p>}

      {resumo && (
        <div className="cartao">
          <strong>{resumo.organizacao}</strong>
          <ul>
            {resumo.criterios.map((c) => (
              <li key={`${c.tipo}-${c.valor}`}>
                {ROTULOS_TIPO[c.tipo]}: {c.valor} — {c.numero_itens} item(ns) nos últimos 30 dias
              </li>
            ))}
          </ul>
        </div>
      )}

      {!erro && (
        <>
          <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>Critérios de monitoramento</h2>
          <form onSubmit={aoCriarCriterio} className="controles-feed">
            <select
              value={tipoCriterio}
              onChange={(e) => setTipoCriterio(e.target.value as api.TipoCriterioMonitoramento)}
            >
              {Object.entries(ROTULOS_TIPO).map(([valor, rotulo]) => (
                <option key={valor} value={valor}>
                  {rotulo}
                </option>
              ))}
            </select>
            <input
              type="text"
              placeholder="valor a monitorar"
              value={valorCriterio}
              onChange={(e) => setValorCriterio(e.target.value)}
            />
            <button type="submit" className="botao" disabled={criandoCriterio}>
              {criandoCriterio ? "Adicionando..." : "Adicionar critério"}
            </button>
          </form>

          {criterios.length === 0 && <p className="texto-suave">Nenhum critério configurado ainda.</p>}
          {criterios.map((c) => {
            const grupo = itensMonitorados[String(c.id)];
            return (
              <div className="cartao" key={c.id}>
                <div className="cartao-meta">
                  <span className="badge-categoria">{ROTULOS_TIPO[c.tipo]}</span>
                  <span>{c.valor}</span>
                  {!c.ativo && <span className="texto-suave">(inativo)</span>}
                </div>
                {grupo && grupo.itens.length > 0 ? (
                  <ul>
                    {grupo.itens.map((item) => (
                      <li key={item.id}>
                        <a href={item.url_fonte_original} target="_blank" rel="noreferrer">
                          {item.titulo}
                        </a>{" "}
                        — {item.nome_fonte}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="texto-suave">Nenhum item encontrado para este critério ainda.</p>
                )}
              </div>
            );
          })}

          <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>Membros da organização</h2>
          <div className="cartao">
            {membros.map((m) => (
              <div key={m.id} className="cartao-meta">
                <span>{m.email}</span>
                <span>{m.papel_na_organizacao === "admin_organizacao" ? "Administrador" : "Membro"}</span>
                {souAdmin && m.email !== usuario?.email && (
                  <button type="button" className="botao botao-perigo" onClick={() => aoRemoverMembro(m.email)}>
                    Remover
                  </button>
                )}
              </div>
            ))}

            {souAdmin && (
              <form onSubmit={aoConvidar} className="controles-feed" style={{ marginTop: "1rem" }}>
                {erroConvite && <p className="mensagem-erro">{erroConvite}</p>}
                <input
                  type="email"
                  placeholder="e-mail do convidado"
                  value={emailConvite}
                  onChange={(e) => setEmailConvite(e.target.value)}
                  required
                />
                <button type="submit" className="botao" disabled={convidando}>
                  {convidando ? "Convidando..." : "Convidar membro"}
                </button>
              </form>
            )}
          </div>
        </>
      )}
    </div>
  );
}
