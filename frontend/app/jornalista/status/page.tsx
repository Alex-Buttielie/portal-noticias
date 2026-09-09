"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useMeuPerfilJornalista, useMinhaSolicitacao, useSalvarPerfilJornalista } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoAreaTexto } from "@/components/ui/FormField";
import { ErrorState, SkeletonCard } from "@/components/ui/Estados";

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
  const solicitacaoQuery = useMinhaSolicitacao();
  const perfilQuery = useMeuPerfilJornalista();
  const salvarPerfil = useSalvarPerfilJornalista();

  const [editandoPerfil, setEditandoPerfil] = useState(false);
  const [miniBioPerfil, setMiniBioPerfil] = useState("");
  const [dadosProfissionaisPerfil, setDadosProfissionaisPerfil] = useState("");

  useEffect(() => {
    if (!carregandoAuth && !token) {
      router.push("/login");
    }
  }, [carregandoAuth, token, router]);

  if (carregandoAuth || solicitacaoQuery.isLoading) return <p className="texto-suave">Carregando...</p>;
  if (solicitacaoQuery.isError) {
    return (
      <ErrorState
        mensagem="Não foi possível carregar sua solicitação."
        aoTentarNovamente={() => void solicitacaoQuery.refetch()}
      />
    );
  }

  const solicitacao = solicitacaoQuery.data ?? null;
  const perfil = perfilQuery.data ?? null;

  function iniciarEdicaoPerfil() {
    if (!perfil) return;
    setMiniBioPerfil(perfil.mini_bio);
    setDadosProfissionaisPerfil(perfil.dados_profissionais);
    setEditandoPerfil(true);
  }

  async function salvarPerfilHandler(evento: FormEvent) {
    evento.preventDefault();
    if (!token) return;
    try {
      await salvarPerfil.mutateAsync({ mini_bio: miniBioPerfil, dados_profissionais: dadosProfissionaisPerfil });
      setEditandoPerfil(false);
      notificar("Perfil profissional atualizado.", "sucesso");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível salvar o perfil.", "erro");
    }
  }

  if (solicitacao === null) {
    return (
      <div className="formulario">
        <h1>Credenciamento de jornalista</h1>
        <p className="texto-suave">Você ainda não solicitou credenciamento.</p>
        <Link href="/jornalista/solicitar" className="botao botao--primaria botao--medio">
          Solicitar agora
        </Link>
      </div>
    );
  }

  return (
    <div className="formulario">
      <h1>Status do seu credenciamento</h1>
      <div className="cartao">
        <Badge variante={solicitacao.status === "aprovado" ? "sucesso" : solicitacao.status === "reprovado" ? "erro" : "neutro"}>
          {ROTULOS_STATUS[solicitacao.status]}
        </Badge>
        {solicitacao.motivo_decisao && (
          <p className="texto-suave" style={{ marginTop: "0.4rem" }}>
            {solicitacao.motivo_decisao}
          </p>
        )}
      </div>
      {solicitacao.status === "aprovado" && (
        <Link href="/comunidade/nova" className="botao botao--primaria botao--medio">
          Escrever uma análise
        </Link>
      )}

      {perfilQuery.isLoading && <SkeletonCard />}
      {perfil && (
        <div className="cartao">
          <h2 className="cartao-titulo">Meu perfil profissional</h2>
          {editandoPerfil ? (
            <form onSubmit={salvarPerfilHandler}>
              <CampoAreaTexto
                id="mini-bio-perfil"
                rotulo="Mini bio"
                rows={3}
                value={miniBioPerfil}
                onChange={(e) => setMiniBioPerfil(e.target.value)}
              />
              <CampoAreaTexto
                id="dados-profissionais-perfil"
                rotulo="Dados profissionais"
                rows={3}
                value={dadosProfissionaisPerfil}
                onChange={(e) => setDadosProfissionaisPerfil(e.target.value)}
              />
              <Button type="submit" carregando={salvarPerfil.isPending}>
                Salvar perfil
              </Button>{" "}
              <Button variante="secundaria" onClick={() => setEditandoPerfil(false)}>
                Cancelar
              </Button>
            </form>
          ) : (
            <>
              <p className="texto-suave">{perfil.mini_bio || "Nenhuma bio cadastrada ainda."}</p>
              <p className="texto-suave">
                {perfil.dados_profissionais || "Nenhum dado profissional cadastrado ainda."}
              </p>
              <Button variante="secundaria" onClick={iniciarEdicaoPerfil}>
                Editar perfil
              </Button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
