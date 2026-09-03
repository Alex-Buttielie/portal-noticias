"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";

const ROTULOS_STATUS: Record<api.StatusCredenciamento, string> = {
  pendente: "Em análise",
  aprovado: "Aprovado — você é um jornalista credenciado",
  reprovado: "Reprovado",
  info_solicitada: "Informação adicional solicitada",
};

export default function PaginaStatusCredenciamento() {
  const router = useRouter();
  const { token, carregando: carregandoAuth } = useAuth();
  const { notificar } = useToast();
  const [solicitacao, setSolicitacao] = useState<api.SolicitacaoCredenciamento | null | undefined>(
    undefined
  );
  const [erro, setErro] = useState<string | null>(null);

  const [perfil, setPerfil] = useState<api.PerfilJornalista | null>(null);
  const [editandoPerfil, setEditandoPerfil] = useState(false);
  const [miniBioPerfil, setMiniBioPerfil] = useState("");
  const [dadosProfissionaisPerfil, setDadosProfissionaisPerfil] = useState("");
  const [salvandoPerfil, setSalvandoPerfil] = useState(false);

  useEffect(() => {
    if (carregandoAuth) return;
    if (!token) {
      router.push("/login");
      return;
    }
    api
      .obterMinhaSolicitacaoCredenciamento(token)
      .then(setSolicitacao)
      .catch((e: unknown) => {
        setErro(e instanceof api.ApiError ? e.message : "Não foi possível carregar sua solicitação.");
      });
    api
      .obterMeuPerfilJornalista(token)
      .then(setPerfil)
      .catch(() => {
        // perfil só existe para quem já foi aprovado — 404 é esperado, não é erro de tela
      });
  }, [token, carregandoAuth, router]);

  function iniciarEdicaoPerfil() {
    if (!perfil) return;
    setMiniBioPerfil(perfil.mini_bio);
    setDadosProfissionaisPerfil(perfil.dados_profissionais);
    setEditandoPerfil(true);
  }

  async function salvarPerfil(evento: FormEvent) {
    evento.preventDefault();
    if (!token) return;
    setSalvandoPerfil(true);
    try {
      const atualizado = await api.atualizarMeuPerfilJornalista(token, {
        mini_bio: miniBioPerfil,
        dados_profissionais: dadosProfissionaisPerfil,
      });
      setPerfil(atualizado);
      setEditandoPerfil(false);
      notificar("Perfil profissional atualizado.", "sucesso");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível salvar o perfil.", "erro");
    } finally {
      setSalvandoPerfil(false);
    }
  }

  if (carregandoAuth || solicitacao === undefined) return <p className="texto-suave">Carregando...</p>;
  if (erro) return <p className="mensagem-erro">{erro}</p>;

  if (solicitacao === null) {
    return (
      <div className="formulario">
        <h1>Credenciamento de jornalista</h1>
        <p className="texto-suave">Você ainda não solicitou credenciamento.</p>
        <Link href="/jornalista/solicitar" className="botao">
          Solicitar agora
        </Link>
      </div>
    );
  }

  return (
    <div className="formulario">
      <h1>Status do seu credenciamento</h1>
      <div className="cartao">
        <strong>{ROTULOS_STATUS[solicitacao.status]}</strong>
        {solicitacao.motivo_decisao && (
          <p className="texto-suave" style={{ marginTop: "0.4rem" }}>
            {solicitacao.motivo_decisao}
          </p>
        )}
      </div>
      {solicitacao.status === "aprovado" && (
        <Link href="/comunidade/nova" className="botao">
          Escrever uma análise
        </Link>
      )}

      {perfil && (
        <div className="cartao" style={{ marginTop: "1.5rem" }}>
          <h2 style={{ fontSize: "1.1rem" }}>Meu perfil profissional</h2>
          {editandoPerfil ? (
            <form onSubmit={salvarPerfil}>
              <div className="campo">
                <label htmlFor="mini-bio-perfil">Mini bio</label>
                <textarea
                  id="mini-bio-perfil"
                  rows={3}
                  value={miniBioPerfil}
                  onChange={(e) => setMiniBioPerfil(e.target.value)}
                />
              </div>
              <div className="campo">
                <label htmlFor="dados-profissionais-perfil">Dados profissionais</label>
                <textarea
                  id="dados-profissionais-perfil"
                  rows={3}
                  value={dadosProfissionaisPerfil}
                  onChange={(e) => setDadosProfissionaisPerfil(e.target.value)}
                />
              </div>
              <button type="submit" className="botao" disabled={salvandoPerfil}>
                {salvandoPerfil ? "Salvando..." : "Salvar perfil"}
              </button>{" "}
              <button type="button" className="botao botao-secundario" onClick={() => setEditandoPerfil(false)}>
                Cancelar
              </button>
            </form>
          ) : (
            <>
              <p className="texto-suave">{perfil.mini_bio || "Nenhuma bio cadastrada ainda."}</p>
              <p className="texto-suave">
                {perfil.dados_profissionais || "Nenhum dado profissional cadastrado ainda."}
              </p>
              <button type="button" className="botao botao-secundario" onClick={iniciarEdicaoPerfil}>
                Editar perfil
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
