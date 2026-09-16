"use client";

import { useMemo, useState } from "react";
import { useAdminAssinaturas } from "@/lib/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { DataTable } from "@/components/ui/Data";
import { ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent } from "@/components/ui/card";

const STATUS = ["", "ativa", "teste", "pagamento_pendente", "inadimplente", "cancelada", "expirada", "encerrada"];
type Ordem = "email-asc" | "email-desc" | "preco-asc" | "preco-desc";

function formatarData(data: string): string {
  const d = new Date(data);
  if (Number.isNaN(d.getTime())) return data;
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" }).format(d);
}

export default function AdminAssinaturasPage() {
  const [statusFiltro, setStatusFiltro] = useState("");
  const [search, setSearch] = useState("");
  const [searchAplicada, setSearchAplicada] = useState("");
  const [page, setPage] = useState(1);
  const [ordem, setOrdem] = useState<Ordem>("email-asc");
  const lista = useAdminAssinaturas({ status: statusFiltro || undefined, search: searchAplicada || undefined, page });

  const linhas = useMemo(() => {
    const copia = [...(lista.data?.results ?? [])];
    copia.sort((a, b) => {
      const [chave, dir] = ordem.split("-") as ["email" | "preco", "asc" | "desc"];
      const va = chave === "email" ? a.user_email.toLowerCase() : a.preco_cobrado;
      const vb = chave === "email" ? b.user_email.toLowerCase() : b.preco_cobrado;
      const cmp = String(va).localeCompare(String(vb), "pt-BR");
      return dir === "asc" ? cmp : -cmp;
    });
    return copia;
  }, [lista.data, ordem]);

  const totalPaginas = lista.data ? Math.max(1, Math.ceil(lista.data.count / Math.max(1, lista.data.results.length))) : 1;

  return (
    <section className="grid gap-6" aria-labelledby="admin-ass-titulo">
      <div className="grid gap-1">
        <h1 id="admin-ass-titulo" className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
          Assinaturas
        </h1>
        <p className="text-sm text-[var(--cor-texto-suave)]">Filtre por status, busque assinantes e confira os valores.</p>
      </div>
      <Card>
        <CardContent className="pt-6">
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              setSearchAplicada(search);
              setPage(1);
            }}
          >
            <div className="min-w-[160px] max-w-xs flex-1">
              <CampoSelecao
                id="admin-ass-status"
                name="admin-ass-status"
                rotulo="Status"
                value={statusFiltro}
                onChange={(e) => {
                  setStatusFiltro(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">todos status</option>
                {STATUS.slice(1).map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </CampoSelecao>
            </div>
            <div className="min-w-[200px] flex-1">
              <CampoTexto
                id="admin-ass-busca"
                name="admin-ass-busca"
                rotulo="Buscar e-mail ou nome"
                placeholder="nome ou e-mail…"
                autoComplete="off"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <Button type="submit" className="h-10">
              Filtrar
            </Button>
            <div className="min-w-[180px] flex-1">
              <CampoSelecao
                id="admin-ass-ordem"
                name="admin-ass-ordem"
                rotulo="Ordenar"
                value={ordem}
                onChange={(e) => setOrdem(e.target.value as Ordem)}
              >
                <option value="email-asc">Usuário (A–Z)</option>
                <option value="email-desc">Usuário (Z–A)</option>
                <option value="preco-asc">Menor preço</option>
                <option value="preco-desc">Maior preço</option>
              </CampoSelecao>
            </div>
          </form>
        </CardContent>
      </Card>

      {lista.isLoading && <SkeletonLista quantidade={3} />}
      {lista.isError && <ErrorState mensagem="Erro ao carregar assinaturas." aoTentarNovamente={() => void lista.refetch()} />}
      {lista.data && (
        <div aria-live="polite">
          <DataTable
            legenda="Assinaturas"
            linhas={linhas}
            colunas={[
              { cabecalho: "Usuário", render: (a) => <span className="text-sm">{a.user_email}</span> },
              { cabecalho: "Plano", render: (a) => a.plan.nome },
              {
                cabecalho: "Status",
                render: (a) => (
                  <Badge variant={a.status === "ativa" ? "success" : a.status === "cancelada" || a.status === "expirada" ? "destructive" : "secondary"}>
                    {a.status}
                  </Badge>
                ),
              },
              { cabecalho: "Preço", render: (a) => a.preco_cobrado },
              { cabecalho: "Desde", render: (a) => formatarData(a.criado_em) },
            ]}
            pagina={page}
            totalPaginas={totalPaginas}
            aoMudarPagina={setPage}
          />
        </div>
      )}
    </section>
  );
}
