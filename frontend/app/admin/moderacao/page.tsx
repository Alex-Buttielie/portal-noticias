"use client";
import { useState } from "react";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useAdminAcaoDenuncia, useAdminDenuncias } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoSelecao } from "@/components/ui/FormField";
import { DataTable } from "@/components/ui/Data";
import { ErrorState, SkeletonLista } from "@/components/ui/Estados";

export default function AdminModeracaoPage() {
  const { notificar } = useToast();
  const [statusFiltro, setStatusFiltro] = useState("");
  const [page, setPage] = useState(1);
  const lista = useAdminDenuncias({ status: statusFiltro || undefined, page });
  const agir = useAdminAcaoDenuncia();

  const totalPaginas = lista.data ? Math.max(1, Math.ceil(lista.data.count / Math.max(1, lista.data.results.length))) : 1;

  async function aplicarAcao(id: number) {
    const motivo = window.prompt("Motivo da ação:");
    if (!motivo) return;
    const tipo =
      window.prompt("Tipo (aviso, remocao_conteudo, bloqueio_temporario, bloqueio_permanente):", "aviso") || "aviso";
    try {
      await agir.mutateAsync({ id, tipo, motivo, procedente: true });
      notificar("Ação aplicada.", "sucesso");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível aplicar a ação.", "erro");
    }
  }

  return (
    <div>
      <h1>Moderação</h1>
      <CampoSelecao
        id="admin-mod-status"
        rotulo="Status"
        value={statusFiltro}
        onChange={(e) => {
          setStatusFiltro(e.target.value);
          setPage(1);
        }}
      >
        <option value="">todos</option>
        <option value="pendente">pendente</option>
        <option value="procedente">procedente</option>
        <option value="improcedente">improcedente</option>
      </CampoSelecao>

      {lista.isLoading && <SkeletonLista quantidade={3} />}
      {lista.isError && (
        <ErrorState mensagem="Erro ao carregar denúncias." aoTentarNovamente={() => void lista.refetch()} />
      )}
      {lista.data && (
        <DataTable
          legenda="Denúncias"
          linhas={lista.data.results}
          colunas={[
            { cabecalho: "#", render: (d) => String(d.id) },
            { cabecalho: "Motivo", render: (d) => d.motivo },
            {
              cabecalho: "Status",
              render: (d) => (
                <Badge variante={d.status === "pendente" ? "neutro" : d.status === "procedente" ? "erro" : "sucesso"}>
                  {d.status}
                </Badge>
              ),
            },
            { cabecalho: "Denunciante", render: (d) => d.denunciante_email },
            { cabecalho: "Alvo", render: (d) => d.alvo_repr ?? "—" },
            {
              cabecalho: "Ação",
              render: (d) => (
                <Button tamanho="pequeno" carregando={agir.isPending} onClick={() => void aplicarAcao(d.id)}>
                  Aplicar ação
                </Button>
              ),
            },
          ]}
          pagina={page}
          totalPaginas={totalPaginas}
          aoMudarPagina={setPage}
        />
      )}
    </div>
  );
}
