"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import {
  useConvidarMembroB2B,
  useCriarCriterioB2B,
  useExcluirCriterioB2B,
  usePainelB2B,
  useRemoverMembroB2B,
} from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { DataTable, StatCard } from "@/components/ui/Data";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";

const ROTULOS_TIPO: Record<api.TipoCriterioMonitoramento, string> = {
  empresa: "Empresa",
  concorrente: "Concorrente",
  setor: "Setor",
  palavra_chave: "Palavra-chave",
};

export default function PaginaEmpresa() {
  const router = useRouter();
  const { token, usuario, carregando: carregandoAuth } = useAuth();
  const { notificar } = useToast();
  const painel = usePainelB2B();
  const criarCriterio = useCriarCriterioB2B(painel.recarregar);
  const excluirCriterio = useExcluirCriterioB2B(painel.recarregar);
  const convidar = useConvidarMembroB2B(painel.recarregar);
  const remover = useRemoverMembroB2B(painel.recarregar);

  const [tipoCriterio, setTipoCriterio] = useState<api.TipoCriterioMonitoramento>("palavra_chave");
  const [valorCriterio, setValorCriterio] = useState("");
  const [emailConvite, setEmailConvite] = useState("");
  const [erroConvite, setErroConvite] = useState<string | null>(null);

  useEffect(() => {
    if (!carregandoAuth && !token) {
      router.push("/login");
    }
  }, [carregandoAuth, token, router]);

  if (carregandoAuth) return <p className="texto-suave">Carregando...</p>;

  const carregando =
    painel.criterios.isLoading || painel.itens.isLoading || painel.resumo.isLoading || painel.membros.isLoading;
  const erroQuery =
    painel.criterios.error ?? painel.itens.error ?? painel.resumo.error ?? painel.membros.error;
  const semOrganizacao =
    erroQuery instanceof api.ApiError && erroQuery.status === 403;

  const criterios = painel.criterios.data ?? [];
  const itensMonitorados = painel.itens.data ?? {};
  const resumo = painel.resumo.data ?? null;
  const membros = painel.membros.data ?? [];

  async function aoCriarCriterio(evento: FormEvent) {
    evento.preventDefault();
    if (!token || !valorCriterio.trim()) return;
    try {
      await criarCriterio.mutateAsync({ tipo: tipoCriterio, valor: valorCriterio.trim() });
      setValorCriterio("");
      notificar("Critério adicionado.", "sucesso");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível criar o critério.", "erro");
    }
  }

  async function aoConvidar(evento: FormEvent) {
    evento.preventDefault();
    if (!token || !emailConvite.trim()) return;
    setErroConvite(null);
    try {
      await convidar.mutateAsync(emailConvite.trim());
      setEmailConvite("");
      notificar("Convite enviado.", "sucesso");
    } catch (e) {
      setErroConvite(e instanceof api.ApiError ? e.message : "Não foi possível convidar este usuário.");
    }
  }

  async function aoRemoverCriterio(id: number, valor: string) {
    const confirmado = window.confirm(`Remover o critério "${valor}"? O monitoramento correspondente para.`);
    if (!confirmado) return;
    try {
      await excluirCriterio.mutateAsync(id);
      notificar("Critério removido.", "info");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível remover o critério.", "erro");
    }
  }

  async function aoRemoverMembro(email: string) {
    if (!token) return;
    const confirmado = window.confirm(`Remover ${email} da organização?`);
    if (!confirmado) return;
    try {
      await remover.mutateAsync(email);
      notificar("Membro removido.", "info");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível remover este membro.", "erro");
    }
  }

  const souAdmin = membros.some(
    (m) => m.email === usuario?.email && m.papel_na_organizacao === "admin_organizacao"
  );

  return (
    <div>
      <h1>Painel da empresa</h1>

      {carregando && <SkeletonLista quantidade={3} />}
      {erroQuery && (
        <ErrorState
          mensagem={
            semOrganizacao
              ? "Sua conta não pertence a nenhuma organização corporativa."
              : "Não foi possível carregar o painel da empresa."
          }
          aoTentarNovamente={() => painel.recarregar()}
        />
      )}

      {!carregando && !erroQuery && (
        <>
          {resumo && (
            <div className="cartao">
              <strong>{resumo.organizacao}</strong>
              <div className="kpi-grid">
                {resumo.criterios.map((c) => (
                  <StatCard
                    key={`${c.tipo}-${c.valor}`}
                    rotulo={`${ROTULOS_TIPO[c.tipo]}: ${c.valor}`}
                    valor={`${c.numero_itens} itens`}
                    detalhe="nos últimos 30 dias"
                  />
                ))}
              </div>
            </div>
          )}

          <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>Critérios de monitoramento</h2>
          <form onSubmit={aoCriarCriterio} className="controles-feed">
            <CampoSelecao
              id="tipo-criterio"
              rotulo="Tipo"
              value={tipoCriterio}
              onChange={(e) => setTipoCriterio(e.target.value as api.TipoCriterioMonitoramento)}
            >
              {Object.entries(ROTULOS_TIPO).map(([valor, rotulo]) => (
                <option key={valor} value={valor}>
                  {rotulo}
                </option>
              ))}
            </CampoSelecao>
            <CampoTexto
              id="valor-criterio"
              rotulo="Valor a monitorar"
              value={valorCriterio}
              onChange={(e) => setValorCriterio(e.target.value)}
            />
            <Button type="submit" carregando={criarCriterio.isPending}>
              Adicionar critério
            </Button>
          </form>

          {criterios.length === 0 && (
            <EmptyState titulo="Nenhum critério configurado" descricao="Adicione o primeiro critério acima." />
          )}
          {criterios.map((c) => {
            const grupo = itensMonitorados[String(c.id)];
            return (
              <div className="cartao" key={c.id}>
                <div className="cartao-meta">
                  <Badge variante="neutro">{ROTULOS_TIPO[c.tipo]}</Badge>
                  <span>{c.valor}</span>
                  {!c.ativo && <Badge variante="erro">Inativo</Badge>}
                  <Button
                    variante="fantasma"
                    tamanho="pequeno"
                    carregando={excluirCriterio.isPending}
                    onClick={() => void aoRemoverCriterio(c.id, c.valor)}
                  >
                    Remover
                  </Button>
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
          <DataTable
            legenda="Membros da organização"
            linhas={membros}
            colunas={[
              { cabecalho: "E-mail", render: (m) => m.email },
              {
                cabecalho: "Papel",
                render: (m) => (
                  <Badge variante={m.papel_na_organizacao === "admin_organizacao" ? "premium" : "neutro"}>
                    {m.papel_na_organizacao === "admin_organizacao" ? "Administrador" : "Membro"}
                  </Badge>
                ),
              },
              {
                cabecalho: "Ações",
                render: (m) =>
                  souAdmin && m.email !== usuario?.email ? (
                    <Button variante="perigo" tamanho="pequeno" carregando={remover.isPending} onClick={() => void aoRemoverMembro(m.email)}>
                      Remover
                    </Button>
                  ) : (
                    <span className="texto-suave">—</span>
                  ),
              },
            ]}
          />

          {souAdmin && (
            <form onSubmit={aoConvidar} className="controles-feed" style={{ marginTop: "1rem" }}>
              {erroConvite && <ErrorState mensagem={erroConvite} />}
              <CampoTexto
                id="email-convite"
                rotulo="E-mail do convidado"
                type="email"
                required
                value={emailConvite}
                onChange={(e) => setEmailConvite(e.target.value)}
              />
              <Button type="submit" carregando={convidar.isPending}>
                Convidar membro
              </Button>
            </form>
          )}
        </>
      )}
    </div>
  );
}
