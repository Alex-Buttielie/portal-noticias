"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
export default function AdminFilaPage() {
  const { token } = useAuth();
  const [statusFiltro, setStatusFiltro] = useState("pendente");
  const [dados, setDados] = useState<api.Paginated<api.AdminFilaItem> | null>(null);
  const [page, setPage] = useState(1);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  async function carregar() {
    if (!token) return;
    setCarregando(true);
    try { setDados(await api.adminListarFila(token, { status: statusFiltro, page })); setErro(null); }
    catch (e) { setErro(e instanceof api.ApiError ? e.message : "Erro ao carregar."); }
    finally { setCarregando(false); }
  }
  useEffect(() => { void carregar(); }, [token, statusFiltro, page]);
  async function decidir(id: number, acao: "aprovar" | "rejeitar") {
    if (!token) return;
    await api.adminDecidirFila(token, id, acao);
    await carregar();
  }
  return (
    <div>
      <h1>Fila editorial</h1>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <select value={statusFiltro} onChange={(e) => { setStatusFiltro(e.target.value); setPage(1); }}>
          <option value="pendente">pendente</option><option value="aprovado">aprovado</option><option value="rejeitado">rejeitado</option><option value="nao_aplicavel">não aplicável</option>
        </select>
      </div>
      {erro && <p className="mensagem-erro">{erro}</p>}
      {carregando ? <p className="texto-suave">Carregando…</p> : (
        <>
          <div className="tabela-wrapper">
            <table className="tabela"><thead><tr><th>Título</th><th>Fonte</th><th>Categoria</th><th>Status</th><th>Ações</th></tr></thead>
              <tbody>{dados?.results.map((it) => (
                <tr key={it.id}><td>{it.titulo}</td><td>{it.nome_fonte}</td><td>{it.categoria}</td><td>{it.status_revisao}</td>
                  <td style={{ display: "flex", gap: 6 }}>
                    <button className="botao" onClick={() => decidir(it.id, "aprovar")}>Aprovar</button>
                    <button className="botao botao-perigo" onClick={() => decidir(it.id, "rejeitar")}>Rejeitar</button>
                  </td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <div className="paginacao">
            <button className="botao botao-secundario" disabled={!dados?.previous} onClick={() => setPage((p) => Math.max(1, p - 1))}>Anterior</button>
            <span className="texto-suave">pág {page} — {dados?.count ?? 0}</span>
            <button className="botao botao-secundario" disabled={!dados?.next} onClick={() => setPage((p) => p + 1)}>Próxima</button>
          </div>
        </>
      )}
    </div>
  );
}
