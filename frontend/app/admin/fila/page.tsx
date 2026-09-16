"use client";

import { useMemo, useState } from "react";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useAdminDecidirFila, useAdminFila } from "@/lib/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CampoSelecao } from "@/components/ui/FormField";
import { DataTable } from "@/components/ui/Data";
import { ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export default function AdminFilaPage() {
  const { notificar } = useToast();
  const [statusFiltro, setStatusFiltro] = useState("pendente");
  const [page, setPage] = useState(1);
  const [ordem, setOrdem] = useState<"az" | "za">("az");
  const [alvo, setAlvo] = useState<{ item: api.AdminFilaItem; acao: "aprovar" | "rejeitar" } | null>(null);
  const fila = useAdminFila({ status: statusFiltro, page });
  const decidir = useAdminDecidirFila();

  const linhas = useMemo(() => {
    const copia = [...(fila.data?.results ?? [])];
    copia.sort((a, b) =>
      ordem === "az" ? a.titulo.localeCompare(b.titulo, "pt-BR") : b.titulo.localeCompare(a.titulo, "pt-BR")
    );
    return copia;
  }, [fila.data, ordem]);

  async function confirmarDecisao() {
    if (!alvo) return;
    try {
      await decidir.mutateAsync({ id: alvo.item.id, acao: alvo.acao });
      notificar(alvo.acao === "aprovar" ? "Item aprovado e publicado." : "Item rejeitado.", "sucesso");
      setAlvo(null);
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível registrar a decisão.", "erro");
    }
  }

  const totalPaginas = fila.data ? Math.max(1, Math.ceil(fila.data.count / Math.max(1, fila.data.results.length))) : 1;

  return (
    <section className="grid gap-6" aria-labelledby="admin-fila-titulo">
      <div className="grid gap-1">
        <h1 id="admin-fila-titulo" className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
          Fila editorial
        </h1>
        <p className="text-sm text-[var(--cor-texto-suave)]">Revise os itens pendentes e decida o que vai ao ar.</p>
      </div>
      <Card>
        <CardContent className="flex flex-wrap gap-3 pt-6">
          <div className="min-w-[200px] max-w-xs flex-1">
            <CampoSelecao
              id="admin-fila-status"
              name="admin-fila-status"
              rotulo="Status"
              value={statusFiltro}
              onChange={(e) => {
                setStatusFiltro(e.target.value);
                setPage(1);
              }}
            >
              <option value="pendente">pendente</option>
              <option value="aprovado">aprovado</option>
              <option value="rejeitado">rejeitado</option>
              <option value="nao_aplicavel">não aplicável</option>
            </CampoSelecao>
          </div>
          <div className="min-w-[180px] max-w-xs flex-1">
            <CampoSelecao
              id="admin-fila-ordem"
              name="admin-fila-ordem"
              rotulo="Ordenar título"
              value={ordem}
              onChange={(e) => setOrdem(e.target.value as "az" | "za")}
            >
              <option value="az">Título (A–Z)</option>
              <option value="za">Título (Z–A)</option>
            </CampoSelecao>
          </div>
        </CardContent>
      </Card>

      {fila.isLoading && <SkeletonLista quantidade={3} />}
      {fila.isError && <ErrorState mensagem="Erro ao carregar a fila." aoTentarNovamente={() => void fila.refetch()} />}
      {fila.data && (
        <div aria-live="polite">
          <DataTable
            legenda="Fila editorial"
            linhas={linhas}
            colunas={[
              { cabecalho: "Título", render: (it) => <span className="line-clamp-2 max-w-[28ch] text-sm font-medium">{it.titulo}</span> },
              { cabecalho: "Fonte", render: (it) => it.nome_fonte },
              { cabecalho: "Categoria", render: (it) => it.categoria },
              {
                cabecalho: "Status",
                render: (it) => (
                  <Badge variant={it.status_revisao === "pendente" ? "secondary" : it.status_revisao === "aprovado" ? "success" : "destructive"}>
                    {it.status_revisao}
                  </Badge>
                ),
              },
              {
                cabecalho: "Ações",
                render: (it) => (
                  <span className="flex gap-2">
                    <Button tamanho="pequeno" loading={decidir.isPending} onClick={() => setAlvo({ item: it, acao: "aprovar" })}>
                      Aprovar
                    </Button>
                    <Button variante="perigo" tamanho="pequeno" loading={decidir.isPending} onClick={() => setAlvo({ item: it, acao: "rejeitar" })}>
                      Rejeitar
                    </Button>
                  </span>
                ),
              },
            ]}
            pagina={page}
            totalPaginas={totalPaginas}
            aoMudarPagina={setPage}
          />
        </div>
      )}

      <Dialog open={alvo !== null} onOpenChange={(aberto) => !aberto && setAlvo(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{alvo?.acao === "aprovar" ? "Aprovar este item?" : "Rejeitar este item?"}</DialogTitle>
            <DialogDescription>
              {alvo?.acao === "aprovar"
                ? "O item aprovado entra no feed do portal."
                : "O item rejeitado sai da fila e não aparece no feed."}{" "}
              {alvo && <span className="font-medium text-[var(--cor-texto)]">“{alvo.item.titulo}”</span>}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAlvo(null)} disabled={decidir.isPending}>
              Voltar
            </Button>
            <Button
              variant={alvo?.acao === "aprovar" ? "default" : "destructive"}
              loading={decidir.isPending}
              onClick={() => void confirmarDecisao()}
            >
              {alvo?.acao === "aprovar" ? "Sim, aprovar" : "Sim, rejeitar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
